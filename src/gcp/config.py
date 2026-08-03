"""Production backend selection — local vs GCP services."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def project_id() -> str:
    return (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
        or os.getenv("PROJECT_ID")
        or ""
    )


def location() -> str:
    return os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION") or "asia-south1"


def storage_backend() -> str:
    return (os.getenv("STORAGE_BACKEND") or "local").strip().lower()


def use_vertex() -> bool:
    return env_bool("VERTEX_AI_ENABLED", False) and bool(project_id())


def use_firestore() -> bool:
    return storage_backend() in {"firestore", "gcp", "cloud"} and bool(project_id())


def use_cloud_logging() -> bool:
    return env_bool("CLOUD_LOGGING_ENABLED", use_firestore())


def use_gcs() -> bool:
    return env_bool("GCS_ENABLED", use_firestore()) or bool(os.getenv("GCS_BUCKET"))


def gcs_bucket() -> str:
    return os.getenv("GCS_BUCKET") or f"{project_id()}-second-unit"


def gcs_release_bucket() -> str:
    return os.getenv("GCS_RELEASE_BUCKET") or f"{project_id()}-second-unit-releases"


def model_name() -> str:
    return os.getenv("VERTEX_AI_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"


ROOT = Path(__file__).resolve().parent.parent.parent
