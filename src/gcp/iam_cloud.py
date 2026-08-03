"""Cloud IAM authorization for release approvals.

Uses IAM Credentials / Policy Troubleshooter when available; falls back to
demo principal map so local + Cloud Run demos always work.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ..iam import DEMO_PRINCIPALS, IAMService
from ..models import ROLE_RELEASING_PRODUCER
from .config import env_bool, project_id


class CloudIAMService(IAMService):
    """Extends demo IAM with optional live Cloud IAM role checks."""

    def __init__(self, principals: Optional[dict] = None):
        super().__init__(principals=principals or dict(DEMO_PRINCIPALS))
        # Optional map: principal email -> extra roles from env JSON
        extra = os.getenv("SECOND_UNIT_IAM_EXTRA_JSON")
        if extra:
            import json

            try:
                data = json.loads(extra)
                for k, v in data.items():
                    row = self.principals.setdefault(k, {"display_name": k, "roles": []})
                    roles = set(row.get("roles") or [])
                    roles.update(v if isinstance(v, list) else [])
                    row["roles"] = list(roles)
            except json.JSONDecodeError:
                pass

    def check_release_authorization(
        self,
        user_identity: str,
        resource: Optional[str] = None,
    ) -> dict[str, Any]:
        base = super().check_release_authorization(user_identity, resource=resource)
        if base.get("authorized"):
            return {**base, "source": "secondunit_principal_map"}

        # Optional live check: if principal is a service account with custom role binding
        if env_bool("CLOUD_IAM_LIVE_CHECK", False) and project_id() and user_identity:
            live = self._live_has_role(user_identity, ROLE_RELEASING_PRODUCER)
            if live is True:
                return {
                    "authorized": True,
                    "role": ROLE_RELEASING_PRODUCER,
                    "reason": "ok",
                    "resource": resource,
                    "identity": user_identity,
                    "source": "cloud_iam",
                }
            if live is False:
                return {
                    **base,
                    "source": "cloud_iam",
                    "reason": base.get("reason") or f"Cloud IAM: lacks {ROLE_RELEASING_PRODUCER}",
                }
        return {**base, "source": "secondunit_principal_map"}

    def _live_has_role(self, member_email: str, role: str) -> Optional[bool]:
        """Best-effort project IAM policy scan for user/serviceAccount members."""
        try:
            from google.cloud import resourcemanager_v3
            from google.iam.v1 import iam_policy_pb2

            # Fallback simpler path via CRM getIamPolicy REST-like client
            from googleapiclient import discovery
            import google.auth

            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            service = discovery.build("cloudresourcemanager", "v1", credentials=creds, cache_discovery=False)
            policy = service.projects().getIamPolicy(resource=project_id(), body={}).execute()
            members_user = {f"user:{member_email}", f"serviceAccount:{member_email}"}
            for binding in policy.get("bindings") or []:
                if binding.get("role") == role:
                    bound = set(binding.get("members") or [])
                    if members_user & bound:
                        return True
            # Also accept legacy owner/editor for emergency demo (off by default)
            if env_bool("CLOUD_IAM_ACCEPT_OWNER", False):
                for binding in policy.get("bindings") or []:
                    if binding.get("role") in {"roles/owner", "roles/editor"}:
                        if members_user & set(binding.get("members") or []):
                            return True
            return False
        except Exception:
            return None
