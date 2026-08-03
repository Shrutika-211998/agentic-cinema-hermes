"""ADK callbacks — hard IAM publish gate + clearance policy injection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.factory import build_services
from src.models import ApprovalStatus, ROLE_RELEASING_PRODUCER


def _state(ctx) -> dict:
    # ADK Context exposes .state mapping
    st = getattr(ctx, "state", None)
    if st is None:
        return {}
    try:
        return st if isinstance(st, dict) else dict(st)
    except Exception:
        return {}


def before_tool_gate(tool, args: dict[str, Any], ctx) -> Optional[dict]:
    """Block publish_release_package unless approved by releasingProducer."""
    name = getattr(tool, "name", None) or getattr(tool, "__name__", "") or str(tool)
    # FunctionTool may wrap function name
    fn = getattr(tool, "func", None) or getattr(tool, "_func", None)
    fn_name = getattr(fn, "__name__", "") if fn else ""
    tool_name = name or fn_name
    if "publish_release_package" not in str(tool_name):
        return None

    state = _state(ctx)
    if state.get("approval_status") != ApprovalStatus.APPROVED.value:
        # Also allow explicit arg override only if IAM says so? No — hard gate.
        return {
            "error": "release_blocked",
            "reason": "Cut is not approved. Route back to the approval gate.",
        }

    svc = build_services()
    auth = svc["iam"].check_release_authorization(
        user_identity=state.get("approver_identity") or args.get("user_identity") or "",
        resource=state.get("edl_uri") or args.get("edl_uri"),
    )
    if not auth.get("authorized"):
        svc["audit"].write_audit_log(
            stage="delivery_denied",
            decision="unauthorized_approver",
            actor=state.get("approver_identity") or "unknown",
            payload={"auth": auth, "args_keys": list(args.keys())},
            audit_trail_id=state.get("audit_trail_id"),
            run_id=state.get("run_id"),
        )
        return {
            "error": "unauthorized",
            "reason": auth.get("reason") or f"Approver lacks {ROLE_RELEASING_PRODUCER}.",
            "auth": auth,
        }
    return None


def after_tool_hook(tool, args: dict[str, Any], ctx, tool_response: dict) -> Optional[dict]:
    """Auto-log clearance flags."""
    name = getattr(tool, "name", None) or ""
    fn = getattr(tool, "func", None)
    fn_name = getattr(fn, "__name__", "") if fn else ""
    tool_name = str(name or fn_name)
    if "check_clip_rights" in tool_name and isinstance(tool_response, dict):
        if tool_response.get("status") and tool_response.get("status") != "cleared":
            svc = build_services()
            state = _state(ctx)
            svc["audit"].write_audit_log(
                stage="clearance_flag",
                decision=str(tool_response.get("status")),
                actor="clearance_officer_agent",
                payload={"asset_id": args.get("asset_id"), "result": tool_response},
                audit_trail_id=state.get("audit_trail_id"),
                run_id=state.get("run_id"),
            )
    return tool_response


def clearance_before_model(ctx, llm_request) -> None:
    """Inject live territory rights policy into Clearance Officer context."""
    state = _state(ctx)
    bp = state.get("brief_params") or {}
    territory = "US"
    if isinstance(bp, dict):
        territory = bp.get("territory") or territory
    elif isinstance(bp, str):
        territory = bp
    try:
        svc = build_services()
        policy = svc["rights"].load_territory_rights_policy(territory)
        # Best-effort append to system instruction
        append = getattr(llm_request, "append_instructions", None) or getattr(
            llm_request, "append_system_context", None
        )
        if callable(append):
            append([policy] if not isinstance(policy, list) else policy)
        else:
            # Fallback: stash on config
            cfg = getattr(llm_request, "config", None)
            if cfg is not None and hasattr(cfg, "system_instruction"):
                existing = cfg.system_instruction or ""
                cfg.system_instruction = f"{existing}\n\n{policy}"
    except Exception:
        pass
    return None
