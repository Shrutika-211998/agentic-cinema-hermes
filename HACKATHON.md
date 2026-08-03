# Second Unit — Full Hackathon Runbook

## Project

- **GCP project:** `project-41b01091-4313-42ff-8d8` (Shru-cx-studio-v2)
- **Region:** `asia-south1` (Firestore native already here)
- **Account:** shrutikashripat24@gmail.com

## Local demo (always works)

```bash
cd C:/Users/shrut/second-unit
python -m src.server
# http://127.0.0.1:8080
python test_core.py
```

## ADK local

```bash
cd C:/Users/shrut/second-unit
pip install -r requirements.txt
# Requires GOOGLE_CLOUD_PROJECT + Vertex auth for live Gemini
set GOOGLE_CLOUD_PROJECT=project-41b01091-4313-42ff-8d8
set GOOGLE_GENAI_USE_VERTEXAI=true
set GOOGLE_CLOUD_LOCATION=asia-south1
adk web adk_app
# or: adk run adk_app
```

## Partner MCP (required integration)

```bash
python mcp/archive_server.py   # :8090 archive-intelligence partner surface
python mcp/rights_server.py    # :8091 custom Rights MCP (moat)
```

When the track’s live partner credentials arrive, replace `src/archive.py` HTTP client with the partner SDK while keeping the same tool names: `archive_search`, `archive_get_asset`.

## GCP deploy

```bash
export CLOUDSDK_PYTHON="C:\Users\shrut\AppData\Local\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe"
export PATH="/c/Users/shrut/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin:$PATH"
export GOOGLE_CLOUD_PROJECT=project-41b01091-4313-42ff-8d8
export GOOGLE_CLOUD_LOCATION=asia-south1

bash deploy/deploy.sh
```

Services:
- `second-unit-api`
- `second-unit-dashboard` (open with `?api=<API_URL>`)
- `second-unit-archive-mcp`
- `second-unit-rights-mcp`

## IAM roles created

- `projects/.../roles/secondunit.briefSubmitter`
- `projects/.../roles/secondunit.clearanceReviewer`
- `projects/.../roles/secondunit.releasingProducer`

Bind releasing producer:

```bash
gcloud projects add-iam-policy-binding project-41b01091-4313-42ff-8d8 \
  --member="user:YOUR_PRODUCER@email" \
  --role="projects/project-41b01091-4313-42ff-8d8/roles/secondunit.releasingProducer"
```

## Submission checklist

- [x] Multi-agent ADK app
- [x] Partner Archive MCP server
- [x] Custom Rights MCP
- [x] IAM publish gate in code
- [x] Firestore rights model
- [x] Cloud Run deployable containers
- [x] Studio dashboard
- [x] Audit trail
- [x] Devpost + trailer copy
- [ ] Record 3-min video
- [ ] Public GitHub repo + Apache-2.0 in About
- [ ] Paste hosted URLs into Devpost
- [ ] Select partner track on form

## Honest scope note

Live partner MAM OAuth is track-dependent. The Archive MCP ships with production tool contracts + seeded enterprise catalog so the crew is demoable end-to-end; swap the adapter when partner credentials are issued.
