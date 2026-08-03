# Second Unit

**Agentic Cinema (Google Cloud) — autonomous studio crew for rights-cleared cuts.**

> Brief → discovery → assembly → clearance → **IAM-governed approval** → delivery

## Live demo (Cloud Run · asia-south1)

| Service | URL |
|---|---|
| **Studio dashboard** | https://second-unit-dashboard-fytheknb4a-el.a.run.app/?api=https://second-unit-api-fytheknb4a-el.a.run.app |
| API | https://second-unit-api-fytheknb4a-el.a.run.app/api/health |
| Partner Archive MCP | https://second-unit-archive-mcp-fytheknb4a-el.a.run.app/health |
| Rights & Clearance MCP | https://second-unit-rights-mcp-fytheknb4a-el.a.run.app/health |

**GCP project:** `project-41b01091-4313-42ff-8d8` · **Region:** `asia-south1`

### Demo beat

1. Open dashboard (Marketing principal default).
2. **Run production** with the sample stadium/Instagram brief.
3. Watch Researcher → Editor → Clearance (restricted clips **swap**).
4. Approve as Marketing → **Denied by IAM**.
5. Switch to **Releasing Producer** → Approve → release package + audit trail.

## Local run

```bash
cd C:/Users/shrut/second-unit
python -m src.server
# http://127.0.0.1:8080
python test_core.py
```

### ADK multi-agent (Gemini / Vertex)

```bash
set GOOGLE_CLOUD_PROJECT=project-41b01091-4313-42ff-8d8
set GOOGLE_GENAI_USE_VERTEXAI=true
set GOOGLE_CLOUD_LOCATION=asia-south1
adk web adk_app
```

### MCP servers

```bash
python mcp/archive_server.py   # partner archive surface :8090
python mcp/rights_server.py    # custom rights moat :8091
```

## Architecture

| Layer | Implementation |
|---|---|
| Reasoning | Gemini on Vertex AI |
| Orchestration | **Google ADK** multi-agent (`adk_app/`) + deterministic `SecondUnitPipeline` |
| Partner MCP | Archive MCP (Iconik/Perfect Memory/VionLabs-compatible tools) |
| Custom MCP | Rights & Clearance MCP over Firestore |
| Governance | Custom IAM roles + `before_tool_callback` publish gate |
| Data | Firestore + GCS |
| Assembly | Cloud Run image with ffmpeg → EDL + proxy |
| Audit | Cloud Logging (+ local JSONL mirror) |
| UI | Studio dashboard |

Custom IAM roles in project:

- `roles/secondunit.briefSubmitter`
- `roles/secondunit.clearanceReviewer`
- `roles/secondunit.releasingProducer`

## Deploy

```bash
export CLOUDSDK_PYTHON="C:\\Users\\shrut\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\platform\\bundledpython\\python.exe"
python deploy/deploy.py
```

See `HACKATHON.md`, `DEVPOST.md`, `TRAILER.md`.

## Tests

```bash
python test_core.py
```

## Repository

https://github.com/Shrutika-211998/agentic-cinema-hermes

## Hackathon submit pack

See **`SUBMIT_NOW.md`** for Devpost copy/paste fields, checklist, and demo script.

## License

Apache-2.0

