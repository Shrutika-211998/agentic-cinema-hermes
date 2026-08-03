# Devpost Submission Kit — Second Unit

## Form fields (copy/paste)

**Project name:** Second Unit

**Tagline:** Brief to rights-cleared cut in minutes, not weeks.

**Built with:**
Gemini, Google Cloud ADK (Agent Development Kit), Vertex AI, Cloud Run, Firestore, Cloud Storage, Cloud Logging, Cloud IAM, Partner Archive MCP, custom Rights & Clearance MCP, ffmpeg

**Elevator pitch (short):**
Second Unit is an autonomous studio crew that turns a media archive and a natural-language creative brief into a rights-cleared, ready-to-publish cut. A multi-agent ADK pipeline handles discovery, assembly, and clearance; a hard Cloud IAM gate blocks publish unless a Releasing Producer approves — enforced in code, not model manners.

**Full description:**

### The problem
Content owners sit on massive archives. Marketing needs a 15–30s cut for social *today*. Finding clips is slow; clearing rights is slower; shipping without clearance is catastrophic.

### The solution
Second Unit closes the loop:

1. **Director** parses the brief  
2. **Researcher** queries the **Partner Archive MCP**  
3. **Editor** assembles EDL + proxy rough-cut + captions (Gemini)  
4. **Clearance Officer** checks every asset via the **Rights MCP**, swaps restricted/unknown clips  
5. **IAM approval gate** — only `roles/secondunit.releasingProducer` unblocks publish  
6. **Distributor** delivers the release package + audit trail  

### Why it’s different
Most “AI over archive” demos stop at search. Second Unit is a **production system**: governed delivery, auditable decisions, and a Studio Head story judges can feel in the deny→approve beat.

### Stack (hackathon-accurate)
- Gemini + Vertex AI  
- Google ADK multi-agent app  
- Partner Archive MCP (archive-intelligence category)  
- Custom Rights & Clearance MCP (moat)  
- Cloud Run, Firestore, GCS, Cloud Logging, custom IAM roles  

### Demo
Open the hosted dashboard. Run as Marketing → Approve (denied) → switch to Releasing Producer → Approve → package ships. Watch the audit trail.

**Live demo URL:**  
https://second-unit-dashboard-fytheknb4a-el.a.run.app/

**API health:**  
https://second-unit-api-fytheknb4a-el.a.run.app/api/health

**Partner Archive MCP:**  
https://second-unit-archive-mcp-fytheknb4a-el.a.run.app/health

**Rights MCP:**  
https://second-unit-rights-mcp-fytheknb4a-el.a.run.app/health

## Video
Follow `TRAILER.md` (3 minutes). Upload unlisted YouTube and paste link.

## Repo checklist before submit
- [ ] Public GitHub repo
- [ ] Apache-2.0 visible in About / LICENSE
- [ ] README has live URLs
- [ ] Architecture diagram (`docs/architecture.html`)
- [ ] Track / partner selection on Devpost form

## Judging map

| Criterion | Where it shows |
|---|---|
| Technological Implementation | ADK crew, dual MCPs, ffmpeg assembly, IAM callback, Gemini |
| Design | Studio dashboard, live crew, clearance report, role-aware gate |
| Potential Impact | Archive → revenue; weeks → minutes; studio catastrophe prevention |
| Quality of Idea | Governed delivery loop + Second Unit framing + clearance-as-governance |
