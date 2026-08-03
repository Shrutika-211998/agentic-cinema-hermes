/* Second Unit studio dashboard */
const API_BASE = (window.SECOND_UNIT_API_BASE
  || new URLSearchParams(location.search).get("api")
  || (window.location.origin.includes("4173") ? "http://127.0.0.1:8080" : "")
).replace(/\/$/, "");

const SAMPLE_BRIEF =
  "Make a 20 second energetic Instagram reel about stadium football celebrations for the US. Keep it rights-safe for social.";

const state = {
  principals: [],
  run: null,
  busy: false,
};

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

function principal() {
  return $("principalSelect").value;
}

function setApiStatus(ok, label) {
  const el = $("apiStatus");
  el.textContent = label;
  el.className = `pill ${ok ? "pill-ok" : "pill-warn"}`;
}

function stageClass(stage) {
  if (stage === "done") return "pill-ok";
  if (stage === "blocked" || stage === "error") return "pill-danger";
  if (stage === "approval") return "pill-accent";
  if (stage && stage !== "idle") return "pill-run";
  return "";
}

function paintCrew(run) {
  const stage = run?.stage || "idle";
  const order = [
    "director",
    "researcher_agent",
    "editor_agent",
    "clearance_officer_agent",
    "distributor_agent",
  ];
  const stageMap = {
    intake: "director",
    discovery: "researcher_agent",
    assembly: "editor_agent",
    clearance: "clearance_officer_agent",
    approval: "clearance_officer_agent",
    delivery: "distributor_agent",
    done: "distributor_agent",
    blocked: "clearance_officer_agent",
    error: "director",
  };
  const active = stageMap[stage] || null;
  const reached = {
    director: ["intake", "discovery", "assembly", "clearance", "approval", "delivery", "done", "blocked"].includes(stage),
    researcher_agent: ["discovery", "assembly", "clearance", "approval", "delivery", "done", "blocked"].includes(stage) || (run?.candidate_clips?.length > 0),
    editor_agent: ["assembly", "clearance", "approval", "delivery", "done", "blocked"].includes(stage) || !!run?.edl_uri,
    clearance_officer_agent: ["clearance", "approval", "delivery", "done", "blocked"].includes(stage) || !!run?.clearance_report?.status,
    distributor_agent: ["delivery", "done"].includes(stage) || !!run?.release_package_uri,
  };

  document.querySelectorAll("#crewList li").forEach((li) => {
    const agent = li.dataset.agent;
    li.classList.remove("active", "done", "blocked");
    const em = li.querySelector(".agent-state");
    if (!run) {
      em.textContent = "idle";
      return;
    }
    if (stage === "blocked" && agent === active) {
      li.classList.add("blocked");
      em.textContent = "blocked";
    } else if (agent === active && stage !== "done") {
      li.classList.add("active");
      em.textContent = stage === "approval" ? "gate" : "working";
    } else if (reached[agent] && (stage === "done" || order.indexOf(agent) < order.indexOf(active))) {
      li.classList.add("done");
      em.textContent = "done";
    } else if (stage === "done") {
      li.classList.add("done");
      em.textContent = "done";
    } else {
      em.textContent = "idle";
    }
  });

  const pill = $("stagePill");
  pill.textContent = stage;
  pill.className = `pill ${stageClass(stage)}`;
}

function colorHash(id) {
  let h = 0;
  for (let i = 0; i < (id || "").length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsl(${hue} 55% 42%)`;
}

function paintCandidates(run) {
  const box = $("candidates");
  const clips = run?.candidate_clips || [];
  $("candCount").textContent = `${clips.length} assets`;
  if (!clips.length) {
    box.className = "thumb-grid empty-state";
    box.textContent = "Run a production to pull archive candidates.";
    return;
  }
  box.className = "thumb-grid";
  box.innerHTML = clips
    .slice(0, 18)
    .map((c) => {
      const tags = (c.mood_tags || c.tags || []).slice(0, 2).join(" · ");
      return `<article class="thumb">
        <div class="art" style="background: linear-gradient(135deg, ${colorHash(c.asset_id)}, #152033)">${(c.asset_id || "").slice(-6).toUpperCase()}</div>
        <div class="body">
          <strong>${escapeHtml(c.title || c.asset_id)}</strong>
          <span>${escapeHtml(tags || "archive")} · ${c.duration_seconds || "?"}s</span>
        </div>
      </article>`;
    })
    .join("");
}

function paintTimeline(run) {
  const box = $("timeline");
  const selected = run?.selected_clips || [];
  const reportItems = Object.fromEntries(
    (run?.clearance_report?.items || []).map((i) => [i.asset_id, i])
  );
  const swapsFrom = new Set((run?.clearance_report?.swaps || []).map((s) => s.to));
  if (!selected.length) {
    box.className = "timeline empty-state";
    box.textContent = "Editor has not cut yet.";
    $("timelineMeta").textContent = "—";
    return;
  }
  const total = selected.reduce(
    (a, c) => a + Math.max(0, (c.out_tc || 0) - (c.in_tc || 0)),
    0
  );
  $("timelineMeta").textContent = `${selected.length} clips · ${total.toFixed(1)}s · ${run?.brief_params?.platform || ""}`;
  box.className = "timeline";
  box.innerHTML = selected
    .map((c, idx) => {
      const item = reportItems[c.asset_id];
      let badge = "";
      if (item?.swapped_from || swapsFrom.has(c.asset_id)) {
        badge = `<span class="badge badge-swap">swapped</span>`;
      } else if (item?.status === "cleared") {
        badge = `<span class="badge badge-ok">cleared</span>`;
      } else if (item && item.status !== "cleared") {
        badge = `<span class="badge badge-bad">${escapeHtml(item.status)}</span>`;
      }
      const dur = Math.max(0, (c.out_tc || 0) - (c.in_tc || 0)).toFixed(1);
      return `<div class="tl-item">
        <div class="ord">${String(idx + 1).padStart(2, "0")}</div>
        <div>
          <strong>${escapeHtml(c.title || c.asset_id)}</strong>
          <small>${escapeHtml(c.asset_id)} · ${dur}s</small>
        </div>
        ${badge}
      </div>`;
    })
    .join("");
}

function paintCutMeta(run) {
  const box = $("cutMeta");
  if (!run?.captions && !run?.edl_uri) {
    box.className = "cut-meta empty-state";
    box.textContent = "No cut yet.";
    return;
  }
  const cap = run.captions || {};
  const tags = (cap.hashtags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("");
  box.className = "cut-meta";
  box.innerHTML = `
    <div class="title">${escapeHtml(cap.title || "Untitled cut")}</div>
    <div class="desc">${escapeHtml(cap.description || "")}</div>
    <div class="tags">${tags}</div>
    <dl class="kv" style="margin-top:8px">
      <dt>EDL</dt><dd>${escapeHtml(run.edl_uri || "—")}</dd>
      <dt>Rough cut</dt><dd>${escapeHtml(run.rough_cut_uri || "—")}</dd>
      <dt>Provider</dt><dd>${escapeHtml(cap.provider || "—")}</dd>
    </dl>
  `;
}

function paintClearance(run) {
  const box = $("clearanceReport");
  const pill = $("clearancePill");
  const report = run?.clearance_report || {};
  const status = run?.clearance_status || report.status || "pending";
  pill.textContent = status;
  pill.className = `pill ${status === "cleared" ? "pill-ok" : status === "blocked" ? "pill-danger" : "pill-warn"}`;

  if (!report.items?.length) {
    box.className = "report empty-state";
    box.textContent = "Clearance Officer has not reported.";
    return;
  }
  box.className = "report";
  const swaps = (report.swaps || [])
    .map((s) => `${s.from} → ${s.to}`)
    .join("<br/>");
  box.innerHTML =
    `<p class="desc" style="margin:0 0 8px;color:#c5d0e4">${escapeHtml(report.summary || "")}</p>` +
    report.items
      .map((i) => {
        const cls = i.status === "cleared" ? "badge-ok" : "badge-bad";
        return `<div class="report-item">
          <header>
            <strong>${escapeHtml(i.asset_id)}</strong>
            <span class="badge ${cls}">${escapeHtml(i.status)}</span>
          </header>
          <p>${escapeHtml(i.notes || "")}${i.swapped_from ? ` · swapped from ${escapeHtml(i.swapped_from)}` : ""}</p>
          <p>source: ${escapeHtml(i.source_of_truth || "—")}</p>
        </div>`;
      })
      .join("") +
    (swaps ? `<div class="swaps"><strong>Swaps</strong><br/>${swaps}</div>` : "");
}

function paintAudit(run) {
  const box = $("auditTrail");
  const events = run?.events || [];
  if (!events.length) {
    box.className = "audit empty-state";
    box.textContent = "No events yet.";
    return;
  }
  box.className = "audit";
  box.innerHTML = events
    .slice()
    .reverse()
    .map((e) => {
      const msg = `${e.stage || ""} · ${e.message || ""}`;
      let cls = "";
      if (/denied|blocked|unauthorized|error|flag/i.test(msg)) cls = "bad";
      else if (/approved|published|cleared|ready/i.test(msg)) cls = "ok";
      else if (/awaiting|started|policy/i.test(msg)) cls = "warn";
      const ts = (e.ts || "").replace("T", " ").replace("Z", "").slice(11, 19);
      return `<div class="audit-row ${cls}"><span class="ts">${escapeHtml(ts)}</span> · <strong>${escapeHtml(e.agent || "")}</strong> — ${escapeHtml(msg)}</div>`;
    })
    .join("");
}

function paintGate(run) {
  const msg = $("gateMessage");
  const approveBtn = $("approveBtn");
  const rejectBtn = $("rejectBtn");
  if (!run) {
    msg.textContent = "Awaiting a cleared cut…";
    approveBtn.disabled = true;
    rejectBtn.disabled = true;
    return;
  }
  if (run.stage === "done") {
    msg.textContent = `Released by ${run.approver_identity || "producer"}. Package ready.`;
    approveBtn.disabled = true;
    rejectBtn.disabled = true;
    return;
  }
  if (run.clearance_status === "cleared" && run.approval_status !== "approved") {
    msg.innerHTML = `<strong>Awaiting Releasing Producer sign-off.</strong><br/>Clearance passed. Current principal: <code>${escapeHtml(principal())}</code>`;
    approveBtn.disabled = false;
    rejectBtn.disabled = false;
    return;
  }
  if (run.clearance_status === "blocked") {
    msg.textContent = "Cut blocked by Clearance — cannot approve for release.";
    approveBtn.disabled = true;
    rejectBtn.disabled = true;
    return;
  }
  msg.textContent = `Stage: ${run.stage}. Approval: ${run.approval_status}.`;
  approveBtn.disabled = true;
  rejectBtn.disabled = run.approval_status === "approved";
}

function paintRelease(run) {
  const box = $("releaseBox");
  if (!run?.release_package_uri) {
    box.className = "release empty-state";
    box.textContent = "Not delivered.";
    return;
  }
  box.className = "release";
  box.innerHTML = `
    <div><strong>Status:</strong> published</div>
    <div style="margin-top:6px"><strong>Package</strong></div>
    <div class="uri">${escapeHtml(run.release_package_uri)}</div>
    <div style="margin-top:8px;color:var(--muted);font-size:0.8rem">Tagline ready: “Brief to rights-cleared cut in minutes, not weeks.”</div>
  `;
}

function paintRun(run) {
  state.run = run;
  $("runIdLabel").textContent = run ? run.run_id : "no active run";
  paintCrew(run);
  paintCandidates(run);
  paintTimeline(run);
  paintCutMeta(run);
  paintClearance(run);
  paintAudit(run);
  paintGate(run);
  paintRelease(run);
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function boot() {
  $("briefInput").value = SAMPLE_BRIEF;
  try {
    const { res, data } = await api("/api/health");
    if (!res.ok) throw new Error("health failed");
    setApiStatus(true, `API · ${data.provider || "ok"}`);
  } catch (e) {
    setApiStatus(false, "API offline");
  }

  try {
    const { data } = await api("/api/principals");
    state.principals = data.principals || [];
    const sel = $("principalSelect");
    sel.innerHTML = state.principals
      .map((p) => {
        const tag = p.can_approve_release ? " · releasingProducer" : "";
        return `<option value="${escapeHtml(p.identity)}">${escapeHtml(p.display_name)}${tag}</option>`;
      })
      .join("");
    // Default demo: start as marketing (for deny beat)
    const mkt = state.principals.find((p) => p.identity.startsWith("marketing"));
    if (mkt) sel.value = mkt.identity;
  } catch (_) {
    $("principalSelect").innerHTML = `<option value="marketing@studio.demo">Marketing</option>
      <option value="producer@studio.demo">Releasing Producer</option>`;
  }

  try {
    const { data } = await api("/api/runs/active");
    if (data.run) paintRun(data.run);
    else paintRun(null);
  } catch (_) {
    paintRun(null);
  }

  $("sampleBtn").onclick = () => {
    $("briefInput").value = SAMPLE_BRIEF;
  };

  $("runBtn").onclick = async () => {
    if (state.busy) return;
    state.busy = true;
    $("runBtn").disabled = true;
    paintCrew({ stage: "intake" });
    try {
      const { res, data } = await api("/api/productions", {
        method: "POST",
        body: JSON.stringify({
          creative_brief: $("briefInput").value,
          submitter: principal(),
        }),
      });
      if (!res.ok) {
        alert(data.message || data.error || "Failed to start production");
        return;
      }
      paintRun(data.run);
    } catch (e) {
      alert("API unreachable. Start: python -m src.server");
    } finally {
      state.busy = false;
      $("runBtn").disabled = false;
    }
  };

  $("approveBtn").onclick = async () => {
    if (!state.run) return;
    const { res, data } = await api(`/api/runs/${state.run.run_id}/approve`, {
      method: "POST",
      body: JSON.stringify({ principal: principal() }),
    });
    if (data.ok === false || res.status === 403) {
      $("gateCard").classList.remove("flash");
      void $("gateCard").offsetWidth;
      $("gateCard").classList.add("flash");
      $("gateMessage").innerHTML = `<strong>Denied by IAM.</strong> ${escapeHtml(
        data.reason || "Approver lacks roles/secondunit.releasingProducer."
      )}<br/><span class="muted">Switch to Releasing Producer and approve again.</span>`;
      if (data.run) paintRun(data.run);
      return;
    }
    if (data.run) paintRun(data.run);
  };

  $("rejectBtn").onclick = async () => {
    if (!state.run) return;
    const { data } = await api(`/api/runs/${state.run.run_id}/reject`, {
      method: "POST",
      body: JSON.stringify({ principal: principal(), reason: "Rejected from dashboard" }),
    });
    if (data.run) paintRun(data.run);
  };

  $("principalSelect").onchange = () => paintGate(state.run);
}

boot();
