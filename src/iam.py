"""Cloud IAM governance layer — custom Second Unit roles + live authorization check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .models import ROLE_BRIEF_SUBMITTER, ROLE_CLEARANCE_REVIEWER, ROLE_RELEASING_PRODUCER


# Demo principals — map to Cloud Identity users in production
DEMO_PRINCIPALS: dict[str, dict[str, Any]] = {
    "marketing@studio.demo": {
        "display_name": "Alex Chen (Marketing)",
        "roles": [ROLE_BRIEF_SUBMITTER],
    },
    "library@studio.demo": {
        "display_name": "Jordan Lee (Library)",
        "roles": [ROLE_BRIEF_SUBMITTER, ROLE_CLEARANCE_REVIEWER],
    },
    "producer@studio.demo": {
        "display_name": "Sam Rivera (Releasing Producer)",
        "roles": [ROLE_RELEASING_PRODUCER, ROLE_CLEARANCE_REVIEWER, ROLE_BRIEF_SUBMITTER],
    },
    "clearance@studio.demo": {
        "display_name": "Riley Okonkwo (Clearance)",
        "roles": [ROLE_CLEARANCE_REVIEWER],
    },
}


@dataclass
class IAMService:
    """In-memory IAM stand-in. Production: Cloud IAM API bindings check."""

    principals: dict[str, dict[str, Any]] = field(default_factory=lambda: dict(DEMO_PRINCIPALS))

    def list_principals(self) -> list[dict[str, Any]]:
        out = []
        for email, meta in self.principals.items():
            out.append(
                {
                    "identity": email,
                    "display_name": meta.get("display_name") or email,
                    "roles": list(meta.get("roles") or []),
                    "can_approve_release": ROLE_RELEASING_PRODUCER in (meta.get("roles") or []),
                }
            )
        return out

    def get_roles(self, user_identity: str) -> list[str]:
        meta = self.principals.get(user_identity) or {}
        return list(meta.get("roles") or [])

    def check_release_authorization(
        self,
        user_identity: str,
        resource: Optional[str] = None,
    ) -> dict[str, Any]:
        """Live IAM check — not cached. Only releasingProducer may approve publish."""
        if not user_identity:
            return {
                "authorized": False,
                "role": None,
                "reason": "missing_approver_identity",
                "resource": resource,
            }
        roles = self.get_roles(user_identity)
        if ROLE_RELEASING_PRODUCER in roles:
            return {
                "authorized": True,
                "role": ROLE_RELEASING_PRODUCER,
                "reason": "ok",
                "resource": resource,
                "identity": user_identity,
            }
        primary = roles[0] if roles else None
        return {
            "authorized": False,
            "role": primary,
            "reason": f"Approver lacks {ROLE_RELEASING_PRODUCER}.",
            "resource": resource,
            "identity": user_identity,
            "held_roles": roles,
        }

    def can_submit_brief(self, user_identity: str) -> bool:
        roles = self.get_roles(user_identity)
        return bool(
            set(roles)
            & {ROLE_BRIEF_SUBMITTER, ROLE_RELEASING_PRODUCER, ROLE_CLEARANCE_REVIEWER}
        )
