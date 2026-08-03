"""GCS helpers for proxies, EDLs, and release packages."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from ..gcp.config import gcs_bucket, gcs_release_bucket, project_id, use_gcs


def _client():
    from google.cloud import storage

    return storage.Client(project=project_id() or None)


def ensure_buckets() -> dict:
    if not use_gcs() and not project_id():
        return {"skipped": True}
    client = _client()
    created = []
    for name in {gcs_bucket(), gcs_release_bucket()}:
        bucket = client.bucket(name)
        if not bucket.exists():
            # default to multi-region US for media demo; override via env later
            client.create_bucket(name)
            created.append(name)
    return {"created": created, "buckets": [gcs_bucket(), gcs_release_bucket()]}


def upload_file(local_path: str | Path, dest_blob: str, *, release: bool = False) -> str:
    """Upload and return gs:// URI."""
    path = Path(local_path)
    client = _client()
    bucket_name = gcs_release_bucket() if release else gcs_bucket()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    ctype, _ = mimetypes.guess_type(path.name)
    blob.upload_from_filename(str(path), content_type=ctype or "application/octet-stream")
    return f"gs://{bucket_name}/{dest_blob}"


def upload_bytes(data: bytes, dest_blob: str, content_type: str = "application/json", *, release: bool = False) -> str:
    client = _client()
    bucket_name = gcs_release_bucket() if release else gcs_bucket()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{bucket_name}/{dest_blob}"


def signed_url(gs_uri: str, minutes: int = 60) -> Optional[str]:
    if not gs_uri.startswith("gs://"):
        return None
    _, _, rest = gs_uri.partition("gs://")
    bucket_name, _, blob_name = rest.partition("/")
    client = _client()
    blob = client.bucket(bucket_name).blob(blob_name)
    try:
        from datetime import timedelta

        return blob.generate_signed_url(expiration=timedelta(minutes=minutes), method="GET")
    except Exception:
        return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
