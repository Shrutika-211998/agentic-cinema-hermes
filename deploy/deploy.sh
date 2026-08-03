#!/usr/bin/env bash
# Deploy Second Unit to Google Cloud (asia-south1)
set -euo pipefail

export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-C:\\Users\\shrut\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\platform\\bundledpython\\python.exe}"
GCLOUD="${GCLOUD:-gcloud.cmd}"

PROJECT="${GOOGLE_CLOUD_PROJECT:-project-41b01091-4313-42ff-8d8}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-south1}"
REPO="${ARTIFACT_REPO:-second-unit}"
BUCKET="${GCS_BUCKET:-${PROJECT}-second-unit}"
RELEASE_BUCKET="${GCS_RELEASE_BUCKET:-${PROJECT}-second-unit-releases}"

echo "==> Project: $PROJECT  Region: $REGION"
"$GCLOUD" config set project "$PROJECT"

echo "==> Ensure Artifact Registry"
"$GCLOUD" artifacts repositories describe "$REPO" --location="$REGION" >/dev/null 2>&1 \
  || "$GCLOUD" artifacts repositories create "$REPO" \
      --repository-format=docker --location="$REGION" --description="Second Unit images"

echo "==> Ensure GCS buckets"
"$GCLOUD" storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1 \
  || "$GCLOUD" storage buckets create "gs://${BUCKET}" --location="$REGION" --uniform-bucket-level-access
"$GCLOUD" storage buckets describe "gs://${RELEASE_BUCKET}" >/dev/null 2>&1 \
  || "$GCLOUD" storage buckets create "gs://${RELEASE_BUCKET}" --location="$REGION" --uniform-bucket-level-access

echo "==> Custom IAM roles"
create_role () {
  local id="$1" file="$2"
  if "$GCLOUD" iam roles describe "$id" --project="$PROJECT" >/dev/null 2>&1; then
    "$GCLOUD" iam roles update "$id" --project="$PROJECT" --file="$file" || true
  else
    "$GCLOUD" iam roles create "$id" --project="$PROJECT" --file="$file" || true
  fi
}
create_role secondunit.briefSubmitter deploy/iam_role_briefSubmitter.yaml
create_role secondunit.clearanceReviewer deploy/iam_role_clearanceReviewer.yaml
create_role secondunit.releasingProducer deploy/iam_role_releasingProducer.yaml

echo "==> Seed Firestore rights ledger"
STORAGE_BACKEND=firestore GOOGLE_CLOUD_PROJECT="$PROJECT" python deploy/seed_firestore.py

IMG_BASE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}"

build_and_deploy () {
  local name="$1" dockerfile="$2" port="$3" extra_env="${4:-}"
  local image="${IMG_BASE}/${name}"
  echo "==> Build $name"
  "$GCLOUD" builds submit --tag "$image" --timeout=1200 --machine-type=e2-highcpu-8 \
    --project="$PROJECT" \
    --pack="" 2>/dev/null || true
  # Standard docker build via Cloud Build
  "$GCLOUD" builds submit --tag "$image" --timeout=1200 --project="$PROJECT" \
    --config=/dev/stdin <<EOF || "$GCLOUD" builds submit --tag "$image" --timeout=1200 .
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build', '-t', '${image}', '-f', '${dockerfile}', '.']
images: ['${image}']
timeout: 1200s
EOF

  local env="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},STORAGE_BACKEND=firestore,VERTEX_AI_ENABLED=true,CLOUD_LOGGING_ENABLED=true,GCS_ENABLED=true,GCS_BUCKET=${BUCKET},GCS_RELEASE_BUCKET=${RELEASE_BUCKET},VERTEX_AI_MODEL=gemini-2.5-flash"
  if [[ -n "$extra_env" ]]; then
    env="${env},${extra_env}"
  fi

  echo "==> Deploy Cloud Run $name"
  "$GCLOUD" run deploy "$name" \
    --image "$image" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --port "$port" \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 5 \
    --set-env-vars "$env" \
    --project "$PROJECT"
}

# Prefer sequential simple deploys with dockerfile flag
deploy_simple () {
  local name="$1" dockerfile="$2" port="$3"
  local image="${IMG_BASE}/${name}:latest"
  echo "==> Cloud Build $name ($dockerfile)"
  "$GCLOUD" builds submit --project="$PROJECT" --timeout=1200 \
    --tag "$image" \
    --gcs-log-dir="gs://${PROJECT}_cloudbuild/logs" \
    . <<'NO' || \
  "$GCLOUD" builds submit --project="$PROJECT" --timeout=1200 --config=<(cat <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-f', '${dockerfile}', '-t', '${image}', '.']
images:
  - '${image}'
timeout: '1200s'
YAML
)
NO
  true
}

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Explicit docker builds via cloudbuild configs
build_one () {
  local name="$1" df="$2" port="$3"
  local image="${IMG_BASE}/${name}"
  cat > /tmp/cb-${name}.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-f', '${df}', '-t', '${image}', '.']
images:
  - '${image}'
timeout: '1800s'
options:
  logging: CLOUD_LOGGING_ONLY
YAML
  echo "==> Building $name"
  "$GCLOUD" builds submit --project="$PROJECT" --config="/tmp/cb-${name}.yaml" --timeout=1800 .
  local env="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},STORAGE_BACKEND=firestore,VERTEX_AI_ENABLED=true,CLOUD_LOGGING_ENABLED=true,GCS_ENABLED=true,GCS_BUCKET=${BUCKET},GCS_RELEASE_BUCKET=${RELEASE_BUCKET},VERTEX_AI_MODEL=gemini-2.5-flash"
  echo "==> Deploying $name"
  "$GCLOUD" run deploy "$name" \
    --image "$image" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --port "$port" \
    --memory 1Gi \
    --cpu 1 \
    --set-env-vars "$env" \
    --project "$PROJECT"
}

build_one second-unit-api Dockerfile 8080
build_one second-unit-archive-mcp Dockerfile.archive-mcp 8090
build_one second-unit-rights-mcp Dockerfile.rights-mcp 8091
build_one second-unit-dashboard Dockerfile.dashboard 8080

API_URL=$("$GCLOUD" run services describe second-unit-api --region="$REGION" --project="$PROJECT" --format='value(status.url)')
echo "==> Patch dashboard with API URL config"
# Redeploy dashboard is static; inject via env is N/A — use query param docs
echo ""
echo "=========================================="
echo "Second Unit deployed"
echo "API:       $API_URL"
echo "Dashboard: $("$GCLOUD" run services describe second-unit-dashboard --region="$REGION" --project="$PROJECT" --format='value(status.url)')"
echo "Archive MCP: $("$GCLOUD" run services describe second-unit-archive-mcp --region="$REGION" --project="$PROJECT" --format='value(status.url)')"
echo "Rights MCP:  $("$GCLOUD" run services describe second-unit-rights-mcp --region="$REGION" --project="$PROJECT" --format='value(status.url)')"
echo "Open dashboard with ?api=$API_URL"
echo "=========================================="
