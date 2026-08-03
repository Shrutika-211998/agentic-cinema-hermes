"""Shared domain models for Second Unit pipeline state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid


class ClearanceStatus(str, Enum):
    PENDING = "pending"
    CLEARED = "cleared"
    BLOCKED = "blocked"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RightsStatus(str, Enum):
    CLEARED = "cleared"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class PipelineStage(str, Enum):
    INTAKE = "intake"
    DISCOVERY = "discovery"
    ASSEMBLY = "assembly"
    CLEARANCE = "clearance"
    APPROVAL = "approval"
    DELIVERY = "delivery"
    DONE = "done"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class BriefParams:
    duration_seconds: int = 30
    platform: str = "instagram"
    mood: str = "energetic"
    subject: str = ""
    territory: str = "US"
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BriefParams":
        return cls(
            duration_seconds=int(data.get("duration_seconds") or 30),
            platform=str(data.get("platform") or "instagram").lower(),
            mood=str(data.get("mood") or "energetic"),
            subject=str(data.get("subject") or ""),
            territory=str(data.get("territory") or "US").upper(),
            constraints=list(data.get("constraints") or []),
        )


@dataclass
class ClipAsset:
    asset_id: str
    title: str
    proxy_uri: str
    duration_seconds: float
    mood_tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    in_tc: float = 0.0
    out_tc: float = 0.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClipAsset":
        return cls(
            asset_id=str(data["asset_id"]),
            title=str(data.get("title") or data["asset_id"]),
            proxy_uri=str(data.get("proxy_uri") or ""),
            duration_seconds=float(data.get("duration_seconds") or 5.0),
            mood_tags=list(data.get("mood_tags") or data.get("tags") or []),
            entities=list(data.get("entities") or []),
            in_tc=float(data.get("in_tc") or 0.0),
            out_tc=float(data.get("out_tc") or data.get("duration_seconds") or 5.0),
            description=str(data.get("description") or ""),
        )


@dataclass
class SelectedClip(ClipAsset):
    order: int = 0

    def usable_duration(self) -> float:
        return max(0.0, self.out_tc - self.in_tc)


@dataclass
class ClearanceItem:
    asset_id: str
    status: str
    license_window: dict[str, Any] = field(default_factory=dict)
    territory: str = ""
    platforms: list[str] = field(default_factory=list)
    source_of_truth: str = ""
    swapped_from: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClearanceReport:
    items: list[ClearanceItem] = field(default_factory=list)
    swaps: list[dict[str, str]] = field(default_factory=list)
    status: str = ClearanceStatus.PENDING.value
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [i.to_dict() for i in self.items],
            "swaps": self.swaps,
            "status": self.status,
            "summary": self.summary,
        }


@dataclass
class AgentEvent:
    stage: str
    agent: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionRun:
    run_id: str
    creative_brief: str
    brief_params: BriefParams
    stage: str = PipelineStage.INTAKE.value
    candidate_clips: list[dict[str, Any]] = field(default_factory=list)
    selected_clips: list[dict[str, Any]] = field(default_factory=list)
    edl_uri: str = ""
    rough_cut_uri: str = ""
    captions: dict[str, Any] = field(default_factory=dict)
    clearance_report: dict[str, Any] = field(default_factory=dict)
    clearance_status: str = ClearanceStatus.PENDING.value
    approval_status: str = ApprovalStatus.PENDING.value
    approver_identity: str = ""
    release_package_uri: str = ""
    audit_trail_id: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def new_id() -> str:
        return f"run_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "creative_brief": self.creative_brief,
            "brief_params": self.brief_params.to_dict(),
            "stage": self.stage,
            "candidate_clips": self.candidate_clips,
            "selected_clips": self.selected_clips,
            "edl_uri": self.edl_uri,
            "rough_cut_uri": self.rough_cut_uri,
            "captions": self.captions,
            "clearance_report": self.clearance_report,
            "clearance_status": self.clearance_status,
            "approval_status": self.approval_status,
            "approver_identity": self.approver_identity,
            "release_package_uri": self.release_package_uri,
            "audit_trail_id": self.audit_trail_id,
            "events": self.events,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionRun":
        bp = data.get("brief_params") or {}
        return cls(
            run_id=str(data["run_id"]),
            creative_brief=str(data.get("creative_brief") or ""),
            brief_params=BriefParams.from_dict(bp if isinstance(bp, dict) else {}),
            stage=str(data.get("stage") or PipelineStage.INTAKE.value),
            candidate_clips=list(data.get("candidate_clips") or []),
            selected_clips=list(data.get("selected_clips") or []),
            edl_uri=str(data.get("edl_uri") or ""),
            rough_cut_uri=str(data.get("rough_cut_uri") or ""),
            captions=dict(data.get("captions") or {}),
            clearance_report=dict(data.get("clearance_report") or {}),
            clearance_status=str(data.get("clearance_status") or ClearanceStatus.PENDING.value),
            approval_status=str(data.get("approval_status") or ApprovalStatus.PENDING.value),
            approver_identity=str(data.get("approver_identity") or ""),
            release_package_uri=str(data.get("release_package_uri") or ""),
            audit_trail_id=str(data.get("audit_trail_id") or ""),
            events=list(data.get("events") or []),
            error=str(data.get("error") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


# Studio IAM role constants (Cloud IAM custom roles in production)
ROLE_BRIEF_SUBMITTER = "roles/secondunit.briefSubmitter"
ROLE_CLEARANCE_REVIEWER = "roles/secondunit.clearanceReviewer"
ROLE_RELEASING_PRODUCER = "roles/secondunit.releasingProducer"

PLATFORM_ASPECT = {
    "instagram": "9:16",
    "reels": "9:16",
    "tiktok": "9:16",
    "youtube": "16:9",
    "broadcast": "16:9",
    "web": "16:9",
}
