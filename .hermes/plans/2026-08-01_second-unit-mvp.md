# Second Unit — local MVP build notes

Built as a credential-free vertical slice of `second-unit-architecture.md`.

## Verified

- 20/20 unit + E2E tests (`python test_core.py`)
- HTTP path: health → production → IAM deny → IAM approve → release package
- Dashboard served from same process on :8080
- Clearance swaps restricted assets (e.g. archive promo → cleared alt)

## Next production steps (when track confirmed)

1. Partner archive MCP auth + wire `ArchiveMCP` to real endpoints
2. ADK app on Vertex Agent Engine using `src/agent_prompts.py`
3. Firestore adapter behind `RightsMCP`
4. Cloud Run ffmpeg job + GCS proxies
5. Cloud IAM custom roles replacing `src/iam.py` demo map
6. Agent Builder / Agentspace front door
