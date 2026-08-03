"""ADK-style callbacks — hard governance gate before publish."""

from __future__ import annotations

from typing import Any, Callable, Optional

from .models import ApprovalStatus


def before_tool_callback(
    tool_name: str,
    args: dict[str, Any],
    state: dict[str, Any],
    *,
    check_release_authorization: Callable[..., dict[str, Any]],
    write_audit_log: Optional[Callable[..., dict[str, Any]]] = None,
) -> Optional[dict[str, Any]]:
    """Block delivery unless cut is approved by an authorized Releasing Producer.

    Returns an error dict to block the tool, or None to allow.
    This is enforced in code so it survives model confusion / jailbreaks.
    """
    if tool_name != "publish_release_package":
        return None

    if state.get("approval_status") != ApprovalStatus.APPROVED.value:
        return {
            "error": "release_blocked",
            "reason": "Cut is not approved. Route back to the approval gate.",
        }

    auth = check_release_authorization(
        user_identity=state.get("approver_identity"),
        resource=state.get("edl_uri"),
    )
    if not auth.get("authorized"):
        if write_audit_log:
            write_audit_log(
                stage="delivery_denied",
                decision="unauthorized_approver",
                actor=state.get("approver_identity") or "unknown",
                payload={"args": args, "auth": auth},
            )
        return {
            "error": "unauthorized",
            "reason": auth.get("reason")
            or "Approver lacks roles/secondunit.releasingProducer.",
            "auth": auth,
        }
    return None


def after_tool_callback(
    tool_name: str,
    args: dict[str, Any],
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    write_audit_log: Optional[Callable[..., dict[str, Any]]] = None,
    normalize_hits: Optional[Callable[[Any], list]] = None,
) -> dict[str, Any]:
    """Normalize archive results; auto-log clearance flags."""
    if tool_name == "archive_search" and normalize_hits:
        state["candidate_clips"] = normalize_hits(result)
    if tool_name == "check_clip_rights" and isinstance(result, dict):
        if result.get("status") != "cleared" and write_audit_log:
            write_audit_log(
                stage="clearance_flag",
                decision=str(result.get("status")),
                actor="clearance_officer_agent",
                payload={"asset_id": args.get("asset_id"), "result": result},
            )
    return result


def on_approval(
    principal: str,
    state: dict[str, Any],
    *,
    check_release_authorization: Callable[..., dict[str, Any]],
    write_audit_log: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Dashboard Approve handler — real authenticated event, not a UI toggle."""
    auth = check_release_authorization(
        user_identity=principal,
        resource=state.get("edl_uri"),
    )
    if not auth.get("authorized"):
        if write_audit_log:
            write_audit_log(
                stage="approval_denied",
                decision="unauthorized_approver",
                actor=principal,
                payload={"auth": auth},
            )
        return {
            "ok": False,
            "approval_status": state.get("approval_status") or ApprovalStatus.PENDING.value,
            "reason": auth.get("reason"),
            "auth": auth,
        }

    state["approval_status"] = ApprovalStatus.APPROVED.value
    state["approver_identity"] = principal
    if write_audit_log:
        write_audit_log(
            stage="approval",
            decision="approved",
            actor=principal,
            payload={"role": auth.get("role"), "resource": state.get("edl_uri")},
        )
    return {
        "ok": True,
        "approval_status": ApprovalStatus.APPROVED.value,
        "approver_identity": principal,
        "auth": auth,
    }
