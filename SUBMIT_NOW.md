# SUBMIT NOW — Second Unit (Agentic Cinema)

Use this file as your single source of truth for Devpost.

## Final links

| What | URL |
|---|---|
| **GitHub (public)** | https://github.com/Shrutika-211998/agentic-cinema-hermes |
| **Live demo dashboard** | https://second-unit-dashboard-fytheknb4a-el.a.run.app/ |
| **API health** | https://second-unit-api-fytheknb4a-el.a.run.app/api/health |
| **Partner Archive MCP** | https://second-unit-archive-mcp-fytheknb4a-el.a.run.app/health |
| **Rights & Clearance MCP** | https://second-unit-rights-mcp-fytheknb4a-el.a.run.app/health |
| **Architecture diagram** | https://second-unit-dashboard-fytheknb4a-el.a.run.app/architecture.html |
| Devpost hackathon | https://agentic-cinema.devpost.com/ |

---

## Devpost form — copy/paste

### Project name
```
Second Unit
```

### Tagline
```
Brief to rights-cleared cut in minutes, not weeks.
```

### Built with (comma-separated)
```
Gemini, Google Cloud ADK, Vertex AI, Cloud Run, Firestore, Cloud Storage, Cloud Logging, Cloud IAM, Partner Archive MCP, Rights & Clearance MCP, Python, ffmpeg
```

### Elevator pitch / short description
```
Second Unit is an autonomous studio crew that turns a media archive and a natural-language creative brief into a rights-cleared, ready-to-publish cut. A multi-agent Google ADK pipeline handles discovery, assembly, and clearance. A hard Cloud IAM gate blocks publish unless a Releasing Producer approves — enforced in code, not model manners. Partner Archive MCP + custom Rights MCP close the loop from brief to governed delivery.
```

### Full description (markdown OK on most Devpost forms)

```markdown
## The problem
Content owners sit on massive media archives. Marketing needs a 15–30s social cut *today*. Finding the right clips is slow; clearing rights is slower; shipping without clearance is a studio catastrophe.

## The solution — close the loop
Second Unit is a production-shaped multi-agent system:

1. **Director** parses the creative brief (duration, platform, mood, territory)
2. **Researcher** queries the **Partner Archive MCP** (archive-intelligence category)
3. **Editor** assembles an EDL + proxy rough-cut and Gemini captions/metadata
4. **Clearance Officer** checks every asset via the **Rights & Clearance MCP**, swaps restricted/unknown clips
5. **IAM approval gate** — only `roles/secondunit.releasingProducer` unblocks publish (`before_tool_callback`)
6. **Distributor** ships the release package + structured audit trail

## Demo beat (3 minutes)
1. Open the live dashboard as Marketing (briefSubmitter)
2. Run: “20s energetic Instagram reel about stadium football celebrations for the US”
3. Watch candidates → cut → clearance swaps on screen
4. Approve as Marketing → **Denied by IAM**
5. Switch to Releasing Producer → Approve → package delivered
6. Scroll the audit trail

**Tagline:** Brief to rights-cleared cut in minutes, not weeks.

## Why judges should care
Most “AI over archive” demos stop at search. Second Unit is a **production system**: governed delivery, auditable decisions, and a Studio Head story you can feel in the deny→approve beat. Leaked or mis-licensed content is a real studio catastrophe — this system *cannot* ship an uncleared or unauthorized cut.

## Stack (hackathon-accurate)
- **Gemini + Vertex AI** for multimodal reasoning / captions
- **Google ADK** multi-agent app (Director + 4 specialist crew)
- **Partner Archive MCP** (required partner integration surface)
- **Custom Rights & Clearance MCP** (differentiator / moat)
- **Cloud Run, Firestore, GCS, Cloud Logging, custom IAM roles**

## Links
- Demo: https://second-unit-dashboard-fytheknb4a-el.a.run.app/
- Repo: https://github.com/Shrutika-211998/agentic-cinema-hermes
- Architecture: https://second-unit-dashboard-fytheknb4a-el.a.run.app/architecture.html
```

### Repo URL
```
https://github.com/Shrutika-211998/agentic-cinema-hermes
```

### Demo URL
```
https://second-unit-dashboard-fytheknb4a-el.a.run.app/
```

### Video
Record using `TRAILER.md` → upload YouTube (unlisted OK) → paste link.

---

## Track / role framing (pick on form)

Primary story for judges: **Studio Head** (IAM governance)  
Also covers: **Director** (multi-agent crew) + **Technical Producer** (MCP integrations)

Partner category: **Archive intelligence** (Iconik / Perfect Memory / VionLabs-compatible tool surface).  
Custom moat: Rights & Clearance MCP you built.

---

## Pre-submit checklist

- [x] Public GitHub repo with code
- [x] Apache-2.0 `LICENSE` in repo
- [x] README with live URLs
- [x] Hosted demo (Cloud Run)
- [x] Partner Archive MCP live
- [x] Rights MCP live
- [x] IAM deny → approve beat works
- [ ] GitHub About: set Website + topics (manual gear icon)
- [ ] 3-min trailer recorded + YouTube link
- [ ] Devpost form filled + submitted
- [ ] Partner track selected on form

### GitHub About (manual — 20 seconds)

https://github.com/Shrutika-211998/agentic-cinema-hermes → ⚙️ About

- Description: `Second Unit — rights-cleared cuts with Gemini + ADK + MCP + IAM gate`
- Website: `https://second-unit-dashboard-fytheknb4a-el.a.run.app/`
- Topics: `agentic-ai` `google-cloud` `gemini` `adk` `hackathon` `mcp`

---

## Team

Shrutika Shripat — Conversational AI & Generative AI Developer
