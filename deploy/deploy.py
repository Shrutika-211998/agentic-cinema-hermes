#!/usr/bin/env python
"""Deploy Second Unit services to Cloud Run + seed Firestore + IAM roles."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "project-41b01091-4313-42ff-8d8")
REGION = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
REPO = os.getenv("ARTIFACT_REPO", "second-unit")
BUCKET = os.getenv("GCS_BUCKET", f"{PROJECT}-second-unit")
RELEASE_BUCKET = os.getenv("GCS_RELEASE_BUCKET", f"{PROJECT}-second-unit-releases")

os.environ.setdefault(
    "CLOUDSDK_PYTHON",
    r"C:\Users\shrut\AppData\Local\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe",
)
GCLOUD = os.environ.get(
    "GCLOUD",
    r"C:\Users\shrut\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
)


def run(args: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    print("+", " ".join(args))
    return subprocess.run(args, check=check, text=True, **kwargs)


def gcloud(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run([GCLOUD, *args], check=check)


def main() -> int:
    os.chdir(ROOT)
    gcloud("config", "set", "project", PROJECT)

    # Artifact Registry
    r = gcloud(
        "artifacts",
        "repositories",
        "describe",
        REPO,
        f"--location={REGION}",
        check=False,
    )
    if r.returncode != 0:
        gcloud(
            "artifacts",
            "repositories",
            "create",
            REPO,
            "--repository-format=docker",
            f"--location={REGION}",
            "--description=Second Unit images",
        )

    # Buckets
    for b in (BUCKET, RELEASE_BUCKET):
        r = gcloud("storage", "buckets", "describe", f"gs://{b}", check=False)
        if r.returncode != 0:
            gcloud(
                "storage",
                "buckets",
                "create",
                f"gs://{b}",
                f"--location={REGION}",
                "--uniform-bucket-level-access",
            )

    # IAM custom roles
    roles = [
        ("secondunit.briefSubmitter", "deploy/iam_role_briefSubmitter.yaml"),
        ("secondunit.clearanceReviewer", "deploy/iam_role_clearanceReviewer.yaml"),
        ("secondunit.releasingProducer", "deploy/iam_role_releasingProducer.yaml"),
    ]
    for role_id, path in roles:
        r = gcloud("iam", "roles", "describe", role_id, f"--project={PROJECT}", check=False)
        if r.returncode == 0:
            gcloud("iam", "roles", "update", role_id, f"--project={PROJECT}", f"--file={path}", check=False)
        else:
            gcloud("iam", "roles", "create", role_id, f"--project={PROJECT}", f"--file={path}", check=False)

    # Seed Firestore
    env = os.environ.copy()
    env["STORAGE_BACKEND"] = "firestore"
    env["GOOGLE_CLOUD_PROJECT"] = PROJECT
    run([sys.executable, "deploy/seed_firestore.py"], env=env, check=False)

    img_base = f"{REGION}-docker.pkg.dev/{PROJECT}/{REPO}"
    services = [
        ("second-unit-api", "Dockerfile", "8080"),
        ("second-unit-archive-mcp", "Dockerfile.archive-mcp", "8090"),
        ("second-unit-rights-mcp", "Dockerfile.rights-mcp", "8091"),
        ("second-unit-dashboard", "Dockerfile.dashboard", "8080"),
    ]

    env_vars = (
        f"GOOGLE_CLOUD_PROJECT={PROJECT},"
        f"GOOGLE_CLOUD_LOCATION={REGION},"
        "STORAGE_BACKEND=firestore,"
        "VERTEX_AI_ENABLED=true,"
        "CLOUD_LOGGING_ENABLED=true,"
        "GCS_ENABLED=true,"
        f"GCS_BUCKET={BUCKET},"
        f"GCS_RELEASE_BUCKET={RELEASE_BUCKET},"
        "VERTEX_AI_MODEL=gemini-2.5-flash"
    )

    urls = {}
    for name, dockerfile, port in services:
        image = f"{img_base}/{name}"
        cloudbuild = f"""steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-f', '{dockerfile}', '-t', '{image}', '.']
images:
  - '{image}'
timeout: '1800s'
options:
  logging: CLOUD_LOGGING_ONLY
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(cloudbuild)
            cfg = f.name
        print(f"==> Building {name}")
        gcloud("builds", "submit", f"--project={PROJECT}", f"--config={cfg}", "--timeout=1800", ".")
        print(f"==> Deploying {name}")
        gcloud(
            "run",
            "deploy",
            name,
            f"--image={image}",
            f"--region={REGION}",
            "--platform=managed",
            "--allow-unauthenticated",
            f"--port={port}",
            "--memory=1Gi",
            "--cpu=1",
            f"--set-env-vars={env_vars}",
            f"--project={PROJECT}",
        )
        out = gcloud(
            "run",
            "services",
            "describe",
            name,
            f"--region={REGION}",
            f"--project={PROJECT}",
            "--format=value(status.url)",
            check=False,
        )
        urls[name] = (out.stdout or "").strip()

    api = urls.get("second-unit-api", "")
    dash = urls.get("second-unit-dashboard", "")
    print("\n========== DEPLOYED ==========")
    for k, v in urls.items():
        print(f"{k}: {v}")
    if api and dash:
        print(f"\nOpen dashboard:\n  {dash}?api={api}")
    print("==============================\n")

    # Write URLs for docs
    (ROOT / "deploy" / "URLS.txt").write_text(
        "\n".join(f"{k}={v}" for k, v in urls.items())
        + (f"\nDASHBOARD_WITH_API={dash}?api={api}\n" if api and dash else "\n"),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
