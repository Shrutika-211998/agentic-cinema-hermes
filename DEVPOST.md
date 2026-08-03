# Second Unit — Agentic Cinema Hackathon Submission

**Tagline:** Brief to rights-cleared cut in minutes, not weeks.

**Devpost track lens:** Studio Head (governance) + Director (multi-agent) + Technical Producer (MCP)

## One-liner

Second Unit is an autonomous studio crew that turns a media archive + natural-language creative brief into a **rights-cleared, ready-to-publish cut**, gated by Cloud IAM human approval — closing the loop from discovery through governed delivery.

## Built with

| Layer | Implementation |
|---|---|
| Reasoning | Gemini on Vertex AI (`gemini-2.5-flash`) |
| Orchestration | Google ADK multi-agent app (`adk_app/`) — Director + Researcher + Editor + Clearance + Distributor |
| Partner MCP | **Archive MCP** (`mcp/archive_server.py`) — archive-intelligence category (Iconik/Perfect Memory/VionLabs-compatible tool surface) |
| Custom MCP | **Rights & Clearance MCP** (`mcp/rights_server.py`) — the moat |
| Governance | Custom IAM roles + `before_tool_callback` publish gate |
| Data | Firestore `rights_ledger` + `territory_rules` + production runs |
| Media | Cloud Storage masters/proxies + release bucket |
| Assembly | Cloud Run + ffmpeg-capable image → EDL + proxy |
| Audit | Cloud Logging structured entries |
| Surface | Studio dashboard (live crew, clearance report, role-aware approval) |

## Demo script (3 minutes)

1. Open Studio dashboard as **Marketing (briefSubmitter)**.
2. Submit: *“20s energetic Instagram reel about stadium football celebrations for the US.”*
3. Researcher pulls archive candidates (Partner MCP).
4. Editor builds EDL + captions; rough-cut artifact appears.
5. Clearance Officer flags restricted/unknown clips via Rights MCP and **swaps** them on camera.
6. Gate: *Awaiting Releasing Producer sign-off.* Marketing clicks Approve → **Denied by IAM**.
7. Switch to **Releasing Producer** → Approve → Distributor publishes release package.
8. Scroll audit trail. Tagline close.

## Why judges should care

Leaked or mis-licensed content is a studio catastrophe. Second Unit **cannot** ship an uncleared or unauthorized cut — enforced in code, not model manners — and proves every decision with an exportable audit trail.

## Links

- **Hosted dashboard:** https://second-unit-dashboard-fytheknb4a-el.a.run.app/?api=https://second-unit-api-fytheknb4a-el.a.run.app
- **API health:** https://second-unit-api-fytheknb4a-el.a.run.app/api/health
- **Partner Archive MCP:** https://second-unit-archive-mcp-fytheknb4a-el.a.run.app/health
- **Rights MCP:** https://second-unit-rights-mcp-fytheknb4a-el.a.run.app/health
- Trailer script: `TRAILER.md`
- Architecture: repo README + original architecture spec

## Team

Shrutika Shripat — Conversational AI & Generative AI Developer

## License

Apache-2.0
