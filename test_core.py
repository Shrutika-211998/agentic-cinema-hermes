"""Behavior tests for Second Unit core domain."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.archive import ArchiveMCP
from src.assembly import assemble_rough_cut, publish_release_package
from src.audit import AuditLog
from src.brief import parse_brief, select_clips_for_duration, score_clip_for_brief
from src.callbacks import before_tool_callback, on_approval
from src.iam import IAMService
from src.models import ROLE_RELEASING_PRODUCER
from src.pipeline import SecondUnitPipeline
from src.rights import RightsMCP
from src.api import SecondUnitAPI


class TestBriefParsing(unittest.TestCase):
    def test_parses_duration_platform_mood_territory(self):
        text = "Make a 30 second energetic Instagram reel about stadium football nights for US"
        result = parse_brief(text, defaults={"force_defaults": True})
        bp = result["brief_params"]
        self.assertEqual(bp["duration_seconds"], 30)
        self.assertEqual(bp["platform"], "instagram")
        self.assertEqual(bp["mood"], "energetic")
        self.assertEqual(bp["territory"], "US")
        self.assertIn("stadium", bp["subject"].lower())

    def test_asks_clarifying_when_duration_missing(self):
        result = parse_brief("Cinematic youtube cut about ocean waves")
        self.assertIn("duration_seconds", result["missing"])
        self.assertTrue(result["clarifying_question"])


class TestArchiveAndRights(unittest.TestCase):
    def setUp(self):
        self.archive = ArchiveMCP(ROOT / "data" / "archive_seed.json")
        self.rights = RightsMCP(
            ROOT / "data" / "rights_ledger.json",
            ROOT / "data" / "territory_rules.json",
        )

    def test_archive_search_returns_real_ids_only(self):
        hits = self.archive.archive_search(concept="stadium football", mood=["energetic"])
        self.assertGreater(len(hits), 0)
        for h in hits:
            detail = self.archive.archive_get_asset(h["asset_id"])
            self.assertNotIn("error", detail)

    def test_archive_never_invents_missing_id(self):
        detail = self.archive.archive_get_asset("clip_does_not_exist")
        self.assertEqual(detail.get("error"), "asset_not_found")

    def test_restricted_asset_not_cleared_for_instagram(self):
        check = self.rights.check_clip_rights("clip_brand_logo_bump_10", "instagram", "US")
        self.assertEqual(check["status"], "restricted")

    def test_unknown_treated_as_not_cleared(self):
        check = self.rights.check_clip_rights("clip_unknown_broll_16", "instagram", "US")
        self.assertIn(check["status"], ("unknown", "restricted"))
        self.assertNotEqual(check["status"], "cleared")

    def test_cleared_asset_ok(self):
        check = self.rights.check_clip_rights("clip_stadium_roar_01", "instagram", "US")
        self.assertEqual(check["status"], "cleared")

    def test_find_alternative_returns_cleared(self):
        alts = self.rights.find_cleared_alternative(
            "clip_trophy_lift_04",
            {"platform": "instagram", "territory": "US", "mood": "celebratory"},
        )
        self.assertGreater(len(alts), 0)
        for alt in alts:
            c = self.rights.check_clip_rights(alt["asset_id"], "instagram", "US")
            self.assertEqual(c["status"], "cleared")

    def test_broadcast_only_press_flash_blocked_on_instagram(self):
        check = self.rights.check_clip_rights("clip_press_flash_18", "instagram", "US")
        self.assertEqual(check["status"], "restricted")


class TestIAMGate(unittest.TestCase):
    def setUp(self):
        self.iam = IAMService()

    def test_brief_submitter_cannot_approve(self):
        auth = self.iam.check_release_authorization("marketing@studio.demo", resource="edl://x")
        self.assertFalse(auth["authorized"])

    def test_releasing_producer_can_approve(self):
        auth = self.iam.check_release_authorization("producer@studio.demo", resource="edl://x")
        self.assertTrue(auth["authorized"])
        self.assertEqual(auth["role"], ROLE_RELEASING_PRODUCER)

    def test_before_tool_blocks_unapproved_publish(self):
        block = before_tool_callback(
            "publish_release_package",
            {},
            {"approval_status": "pending", "approver_identity": "producer@studio.demo"},
            check_release_authorization=self.iam.check_release_authorization,
        )
        self.assertIsNotNone(block)
        self.assertEqual(block["error"], "release_blocked")

    def test_before_tool_blocks_unauthorized_even_if_approved_flag(self):
        block = before_tool_callback(
            "publish_release_package",
            {},
            {
                "approval_status": "approved",
                "approver_identity": "marketing@studio.demo",
                "edl_uri": "edl://x",
            },
            check_release_authorization=self.iam.check_release_authorization,
        )
        self.assertIsNotNone(block)
        self.assertEqual(block["error"], "unauthorized")

    def test_on_approval_denies_submitter(self):
        state = {"approval_status": "pending", "edl_uri": "edl://x"}
        result = on_approval(
            "marketing@studio.demo",
            state,
            check_release_authorization=self.iam.check_release_authorization,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(state["approval_status"], "pending")

    def test_on_approval_allows_producer(self):
        state = {"approval_status": "pending", "edl_uri": "edl://x"}
        result = on_approval(
            "producer@studio.demo",
            state,
            check_release_authorization=self.iam.check_release_authorization,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(state["approval_status"], "approved")


class TestAssemblyAndSelection(unittest.TestCase):
    def test_select_clips_fits_duration(self):
        candidates = [
            {"asset_id": f"a{i}", "title": f"Clip {i}", "duration_seconds": 5, "mood_tags": ["energetic"]}
            for i in range(10)
        ]
        selected = select_clips_for_duration(
            candidates, {"duration_seconds": 15, "mood": "energetic", "subject": "clip"}
        )
        total = sum(float(c["out_tc"]) - float(c["in_tc"]) for c in selected)
        self.assertGreaterEqual(total, 10)
        self.assertLessEqual(total, 25)

    def test_assemble_writes_edl(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assemble_rough_cut(
                [
                    {
                        "asset_id": "clip_a",
                        "title": "A",
                        "proxy_uri": "gs://x/a.mp4",
                        "in_tc": 0,
                        "out_tc": 3,
                    },
                    {
                        "asset_id": "clip_b",
                        "title": "B",
                        "proxy_uri": "gs://x/b.mp4",
                        "in_tc": 0,
                        "out_tc": 4,
                    },
                ],
                platform="instagram",
                run_id="test",
                output_dir=tmp,
            )
            self.assertTrue(Path(result["edl_uri"]).exists())
            edl = json.loads(Path(result["edl_uri"]).read_text(encoding="utf-8"))
            self.assertEqual(edl["event_count"] if "event_count" in edl else len(edl["events"]), 2)
            self.assertAlmostEqual(edl["total_duration_seconds"], 7.0)


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.store = root / "store.json"
        self.out = root / "output"
        self.audit_path = root / "audit.jsonl"
        self.api = SecondUnitAPI(
            data_path=self.store,
            archive=ArchiveMCP(ROOT / "data" / "archive_seed.json"),
            rights=RightsMCP(
                ROOT / "data" / "rights_ledger.json",
                ROOT / "data" / "territory_rules.json",
            ),
            iam=IAMService(),
            audit=AuditLog(self.audit_path),
            output_dir=self.out,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pipeline_reaches_approval_gate_cleared(self):
        run = self.api.start_production(
            "Create a 20 second energetic Instagram cut about stadium football celebrations in the US",
            submitter="marketing@studio.demo",
        )
        self.assertFalse(run.get("error"), msg=run.get("error"))
        self.assertEqual(run["clearance_status"], "cleared")
        self.assertEqual(run["stage"], "approval")
        self.assertGreater(len(run["candidate_clips"]), 0)
        self.assertGreater(len(run["selected_clips"]), 0)
        self.assertTrue(run["edl_uri"])
        # All selected assets must be cleared
        for clip in run["selected_clips"]:
            check = self.api.check_rights(clip["asset_id"], "instagram", "US")
            self.assertEqual(check["status"], "cleared", msg=clip["asset_id"])

    def test_deny_then_approve_beat(self):
        run = self.api.start_production(
            "Make a 15s uplifting youtube short about team training and sunrise runs for US",
            submitter="marketing@studio.demo",
        )
        run_id = run["run_id"]

        denied = self.api.approve_run(run_id, "marketing@studio.demo")
        self.assertFalse(denied.get("ok"))
        self.assertIn("releasingProducer", (denied.get("reason") or "") + str(denied.get("auth")))

        # Still not delivered
        mid = self.api.get_run(run_id)
        self.assertNotEqual(mid["stage"], "done")
        self.assertFalse(mid.get("release_package_uri"))

        approved = self.api.approve_run(run_id, "producer@studio.demo")
        self.assertTrue(approved.get("ok"))
        final = approved["run"]
        self.assertEqual(final["approval_status"], "approved")
        self.assertEqual(final["stage"], "done")
        self.assertTrue(final["release_package_uri"])
        self.assertTrue(Path(final["release_package_uri"]).exists())

        # Audit trail exists
        audit = self.api.get_audit(run_id)
        self.assertGreater(len(audit), 3)
        decisions = {e.get("decision") for e in audit}
        self.assertTrue(any("unauth" in str(d) or d == "unauthorized_approver" for d in decisions) or any(
            e.get("stage") == "approval_denied" for e in audit
        ))

    def test_publish_cannot_bypass_gate(self):
        run = self.api.start_production(
            "30s cinematic instagram cut about ocean waves",
            submitter="library@studio.demo",
        )
        # Force delivery without approval
        delivered = self.api.deliver_run(run["run_id"])
        self.assertNotEqual(delivered.get("stage"), "done")
        self.assertTrue(delivered.get("error"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
