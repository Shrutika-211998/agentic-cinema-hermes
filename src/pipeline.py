"""Multi-agent crew pipeline — Director sequential orchestration.

Mirrors ADK Sequential Pipeline + governance gate. Agents are deterministic
specialists with optional Gemini for brief enrichment later.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from .archive import ArchiveMCP
from .assembly import assemble_rough_cut, publish_release_package
from .audit import AuditLog, now_iso
from .brief import parse_brief, select_clips_for_duration
from .callbacks import before_tool_callback, on_approval
from .captions import generate_captions_metadata
from .iam import IAMService
from .models import (
    ApprovalStatus,
    ClearanceStatus,
    PipelineStage,
    ProductionRun,
)
from .rights import RightsMCP


class SecondUnitPipeline:
    """Director-owned production pipeline."""

    def __init__(
        self,
        archive: Optional[ArchiveMCP] = None,
        rights: Optional[RightsMCP] = None,
        iam: Optional[IAMService] = None,
        audit: Optional[AuditLog] = None,
        output_dir: Optional[str] = None,
    ):
        self.archive = archive or ArchiveMCP()
        self.rights = rights or RightsMCP()
        self.iam = iam or IAMService()
        self.audit = audit or AuditLog()
        self.output_dir = output_dir

    # ── tool wrappers (logged + callback-aware) ──────────────────────────

    def _log(
        self,
        run: ProductionRun,
        stage: str,
        decision: str,
        actor: str,
        payload: Optional[dict] = None,
    ) -> None:
        self.audit.write_audit_log(
            stage=stage,
            decision=decision,
            actor=actor,
            payload=payload or {},
            audit_trail_id=run.audit_trail_id,
            run_id=run.run_id,
        )
        run.events.append(
            {
                "ts": now_iso(),
                "stage": stage,
                "agent": actor,
                "message": decision,
                "payload": payload or {},
            }
        )
        run.updated_at = now_iso()

    def _tool_publish(self, run: ProductionRun, metadata: dict) -> dict[str, Any]:
        state = {
            "approval_status": run.approval_status,
            "approver_identity": run.approver_identity,
            "edl_uri": run.edl_uri,
        }
        args = {
            "edl_uri": run.edl_uri,
            "rough_cut_uri": run.rough_cut_uri,
            "metadata": metadata,
            "platform": run.brief_params.platform,
        }
        block = before_tool_callback(
            "publish_release_package",
            args,
            state,
            check_release_authorization=self.iam.check_release_authorization,
            write_audit_log=lambda **kw: self.audit.write_audit_log(
                audit_trail_id=run.audit_trail_id, run_id=run.run_id, **kw
            ),
        )
        if block:
            return block
        return publish_release_package(
            edl_uri=run.edl_uri,
            rough_cut_uri=run.rough_cut_uri,
            metadata=metadata,
            platform=run.brief_params.platform,
            clearance_report=run.clearance_report,
            run_id=run.run_id,
            output_dir=self.output_dir,
        )

    # ── agents ───────────────────────────────────────────────────────────

    def intake(self, creative_brief: str, defaults: Optional[dict] = None) -> ProductionRun:
        """Director: parse brief into brief_params."""
        from .models import BriefParams

        parsed = parse_brief(creative_brief, defaults={**(defaults or {}), "force_defaults": True})
        run = ProductionRun(
            run_id=ProductionRun.new_id(),
            creative_brief=creative_brief,
            brief_params=BriefParams.from_dict(parsed["brief_params"]),
            stage=PipelineStage.INTAKE.value,
            audit_trail_id=self.audit.new_trail_id(),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        self._log(
            run,
            stage="intake",
            decision="brief_parsed",
            actor="director",
            payload={"brief_params": run.brief_params.to_dict(), "aspect": parsed.get("aspect_ratio")},
        )
        return run

    def researcher_agent(self, run: ProductionRun) -> ProductionRun:
        """Discover candidate clips via partner archive MCP only."""
        run.stage = PipelineStage.DISCOVERY.value
        bp = run.brief_params.to_dict()
        self._log(run, "discovery", "research_started", "researcher_agent", {"brief": bp})

        hits = self.archive.archive_search(
            concept=bp.get("subject") or run.creative_brief,
            mood=[bp.get("mood")] if bp.get("mood") else [],
            entities=_entities_from_subject(bp.get("subject") or ""),
            limit=24,
        )
        # Enrich with get_asset
        candidates = []
        for hit in hits:
            detail = self.archive.archive_get_asset(hit["asset_id"])
            if detail.get("error"):
                continue
            candidates.append({**hit, **{k: v for k, v in detail.items() if k != "error"}})

        # If sparse, broaden
        if len(candidates) < 4:
            broad = self.archive.archive_search(concept="", mood=[], entities=[], limit=20)
            seen = {c["asset_id"] for c in candidates}
            for hit in broad:
                if hit["asset_id"] in seen:
                    continue
                detail = self.archive.archive_get_asset(hit["asset_id"])
                if not detail.get("error"):
                    candidates.append({**hit, **detail})
                if len(candidates) >= 12:
                    break

        run.candidate_clips = candidates
        self._log(
            run,
            "discovery",
            f"candidates_ready:{len(candidates)}",
            "researcher_agent",
            {"count": len(candidates), "asset_ids": [c.get("asset_id") for c in candidates[:12]]},
        )
        return run

    def editor_agent(self, run: ProductionRun) -> ProductionRun:
        """Sequence clips, assemble rough cut, generate captions."""
        run.stage = PipelineStage.ASSEMBLY.value
        bp = run.brief_params.to_dict()
        self._log(run, "assembly", "edit_started", "editor_agent", {})

        if not run.candidate_clips:
            run.stage = PipelineStage.ERROR.value
            run.error = "No candidate clips to edit."
            self._log(run, "assembly", "edit_failed_no_candidates", "editor_agent", {})
            return run

        selected = select_clips_for_duration(run.candidate_clips, bp)
        run.selected_clips = selected

        assembly = assemble_rough_cut(
            selected,
            platform=bp.get("platform") or "instagram",
            run_id=run.run_id,
            output_dir=self.output_dir,
        )
        run.edl_uri = assembly["edl_uri"]
        run.rough_cut_uri = assembly["rough_cut_uri"]

        captions = generate_captions_metadata(run.rough_cut_uri, bp, selected)
        run.captions = captions

        self._log(
            run,
            "assembly",
            "rough_cut_ready",
            "editor_agent",
            {
                "selected": len(selected),
                "edl_uri": run.edl_uri,
                "rough_cut_uri": run.rough_cut_uri,
                "duration": assembly.get("total_duration_seconds"),
                "title": captions.get("title"),
            },
        )
        return run

    def clearance_officer_agent(self, run: ProductionRun) -> ProductionRun:
        """Verify rights; swap restricted/unknown; emit clearance report."""
        run.stage = PipelineStage.CLEARANCE.value
        bp = run.brief_params.to_dict()
        platform = bp.get("platform") or "instagram"
        territory = bp.get("territory") or "US"
        self._log(run, "clearance", "clearance_started", "clearance_officer_agent", {
            "platform": platform, "territory": territory
        })

        # Inject territory policy into decision context (before_model_callback seam)
        policy = self.rights.load_territory_rights_policy(territory)
        self._log(run, "clearance", "policy_loaded", "clearance_officer_agent", {"policy_preview": policy[:240]})

        items = []
        swaps = []
        selected = list(run.selected_clips)
        changed = False

        for idx, clip in enumerate(list(selected)):
            asset_id = clip.get("asset_id")
            check = self.rights.check_clip_rights(asset_id, platform, territory)
            if check.get("status") != "cleared":
                self._log(
                    run,
                    "clearance_flag",
                    str(check.get("status")),
                    "clearance_officer_agent",
                    {"asset_id": asset_id, "reason": check.get("reason")},
                )
                alts = self.rights.find_cleared_alternative(asset_id, bp, limit=5)
                swapped = False
                for alt in alts:
                    alt_id = alt["asset_id"]
                    # Already in timeline?
                    if any(s.get("asset_id") == alt_id for s in selected):
                        continue
                    detail = self.archive.archive_get_asset(alt_id)
                    if detail.get("error"):
                        continue
                    # Preserve timing budget
                    new_clip = {
                        **detail,
                        "order": clip.get("order", idx),
                        "in_tc": 0.0,
                        "out_tc": float(clip.get("out_tc") or detail.get("duration_seconds") or 5),
                    }
                    # clamp out_tc to asset duration
                    dur = float(detail.get("duration_seconds") or new_clip["out_tc"])
                    new_clip["out_tc"] = min(new_clip["out_tc"], dur)
                    selected[idx] = new_clip
                    swaps.append({"from": asset_id, "to": alt_id, "reason": check.get("reason")})
                    check = self.rights.check_clip_rights(alt_id, platform, territory)
                    check["swapped_from"] = asset_id
                    swapped = True
                    changed = True
                    self._log(
                        run,
                        "clearance",
                        "asset_swapped",
                        "clearance_officer_agent",
                        {"from": asset_id, "to": alt_id},
                    )
                    break
                if not swapped:
                    items.append(
                        {
                            "asset_id": asset_id,
                            "status": check.get("status"),
                            "license_window": check.get("license_window") or {},
                            "territory": territory,
                            "platforms": check.get("platforms") or [],
                            "source_of_truth": check.get("source"),
                            "notes": check.get("reason") or "could not find cleared alternative",
                            "swapped_from": None,
                        }
                    )
                    continue

            items.append(
                {
                    "asset_id": check.get("asset_id") or selected[idx].get("asset_id"),
                    "status": check.get("status"),
                    "license_window": check.get("license_window") or {},
                    "territory": territory,
                    "platforms": check.get("platforms") or [],
                    "source_of_truth": check.get("source"),
                    "notes": check.get("reason") or "ok",
                    "swapped_from": check.get("swapped_from"),
                }
            )

        run.selected_clips = selected
        if changed:
            # Re-assemble after timeline change
            assembly = assemble_rough_cut(
                selected,
                platform=platform,
                run_id=run.run_id,
                output_dir=self.output_dir,
            )
            run.edl_uri = assembly["edl_uri"]
            run.rough_cut_uri = assembly["rough_cut_uri"]
            run.captions = generate_captions_metadata(run.rough_cut_uri, bp, selected)
            self._log(run, "clearance", "reassembled_after_swaps", "clearance_officer_agent", {
                "swaps": len(swaps)
            })

        all_cleared = all(i.get("status") == "cleared" for i in items) and len(items) > 0
        status = ClearanceStatus.CLEARED.value if all_cleared else ClearanceStatus.BLOCKED.value
        report = {
            "items": items,
            "swaps": swaps,
            "status": status,
            "summary": (
                f"All {len(items)} assets cleared for {platform}/{territory}."
                if all_cleared
                else f"Blocked: {sum(1 for i in items if i.get('status') != 'cleared')} asset(s) not cleared."
            ),
            "policy_territory": territory,
        }
        run.clearance_report = report
        run.clearance_status = status
        run.stage = PipelineStage.APPROVAL.value if all_cleared else PipelineStage.BLOCKED.value

        self._log(
            run,
            "clearance",
            f"clearance_{status}",
            "clearance_officer_agent",
            {"report_summary": report["summary"], "swaps": swaps},
        )
        return run

    def approve(
        self,
        run: ProductionRun,
        principal: str,
    ) -> tuple[ProductionRun, dict[str, Any]]:
        """Human approval gate with live IAM check."""
        if run.clearance_status != ClearanceStatus.CLEARED.value:
            result = {
                "ok": False,
                "reason": "Cut is not cleared. Clearance must pass before approval.",
                "clearance_status": run.clearance_status,
            }
            self._log(run, "approval_denied", "not_cleared", principal, result)
            return run, result

        state = {
            "approval_status": run.approval_status,
            "approver_identity": run.approver_identity,
            "edl_uri": run.edl_uri,
        }
        result = on_approval(
            principal,
            state,
            check_release_authorization=self.iam.check_release_authorization,
            write_audit_log=lambda **kw: self.audit.write_audit_log(
                audit_trail_id=run.audit_trail_id, run_id=run.run_id, **kw
            ),
        )
        if result.get("ok"):
            run.approval_status = ApprovalStatus.APPROVED.value
            run.approver_identity = principal
            self._log(run, "approval", "approved", principal, {"role": result.get("auth", {}).get("role")})
        else:
            self._log(run, "approval_denied", "unauthorized", principal, result)
        return run, result

    def reject(self, run: ProductionRun, principal: str, reason: str = "") -> ProductionRun:
        run.approval_status = ApprovalStatus.REJECTED.value
        run.approver_identity = principal
        run.stage = PipelineStage.BLOCKED.value
        self._log(run, "approval", "rejected", principal, {"reason": reason})
        return run

    def distributor_agent(self, run: ProductionRun) -> ProductionRun:
        """Package and deliver — only after approved + IAM ok (callback enforced)."""
        run.stage = PipelineStage.DELIVERY.value
        self._log(run, "delivery", "delivery_started", "distributor_agent", {})

        result = self._tool_publish(run, metadata=run.captions or {})
        if result.get("error"):
            run.error = f"{result.get('error')}: {result.get('reason')}"
            run.stage = PipelineStage.BLOCKED.value
            self._log(run, "delivery_denied", result.get("error"), "distributor_agent", result)
            return run

        run.release_package_uri = result.get("release_package_uri") or ""
        run.stage = PipelineStage.DONE.value
        self._log(
            run,
            "delivery",
            "published",
            "distributor_agent",
            {
                "release_package_uri": run.release_package_uri,
                "approver": run.approver_identity,
            },
        )
        return run

    def run_until_approval_gate(self, creative_brief: str, defaults: Optional[dict] = None) -> ProductionRun:
        """Director full pipeline through clearance; stops at human approval gate."""
        run = self.intake(creative_brief, defaults=defaults)
        self._log(run, "pipeline", "delegating_researcher", "director", {})
        run = self.researcher_agent(run)
        if run.stage == PipelineStage.ERROR.value:
            return run
        self._log(run, "pipeline", "delegating_editor", "director", {})
        run = self.editor_agent(run)
        if run.stage == PipelineStage.ERROR.value:
            return run
        self._log(run, "pipeline", "delegating_clearance", "director", {})
        run = self.clearance_officer_agent(run)
        if run.clearance_status == ClearanceStatus.CLEARED.value:
            self._log(
                run,
                "pipeline",
                "awaiting_releasing_producer_signoff",
                "director",
                {"message": "Awaiting Releasing Producer sign-off."},
            )
        return run

    def complete_delivery(self, run: ProductionRun) -> ProductionRun:
        """Director: only routes to distributor when approval_status == approved."""
        if run.approval_status != ApprovalStatus.APPROVED.value:
            self._log(
                run,
                "pipeline",
                "delivery_refused_not_approved",
                "director",
                {"approval_status": run.approval_status},
            )
            run.error = "Director refuses delivery: approval_status is not approved."
            return run
        self._log(run, "pipeline", "delegating_distributor", "director", {})
        return self.distributor_agent(run)


def _entities_from_subject(subject: str) -> list[str]:
    import re

    stop = {"with", "from", "that", "this", "into", "over", "under", "about", "for", "the", "and"}
    tokens = [t for t in re.split(r"\W+", subject) if len(t) > 3 and t.lower() not in stop]
    return tokens[:6]
