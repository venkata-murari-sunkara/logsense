function statCard(label, value, sub = "", tooltip = "") {
  return `
    <div class="ls-metric-box" ${tooltip ? `title="${tooltip}"` : ""}>
      <div class="ls-metric-label">${label}</div>
      <div class="ls-metric-value">${value}</div>
      ${sub ? `<div class="ls-metric-sub">${sub}</div>` : ""}
    </div>`;
}

async function loadStats() {
  const grid = document.getElementById("stats-grid");
  const accuracyBox = document.getElementById("accuracy-box");
  try {
    const stats = await api.stats();
    grid.innerHTML = [
      statCard(
        "Blocks monitored",
        stats.total_blocks.toLocaleString(),
        "Every system event on record",
        "Each 'block' is one unit of system activity the AI can check"
      ),
      statCard(
        "Confirmed past problems",
        stats.anomaly_count.toLocaleString(),
        `${((stats.anomaly_count / stats.total_blocks) * 100).toFixed(2)}% of all activity · ground-truth anomalies`,
        "Verified real incidents from historical records, not AI guesses"
      ),
      statCard(
        "Flagged for review",
        stats.flagged_unreviewed.toLocaleString(),
        `Awaiting review, out of ${stats.flagged_by_model.toLocaleString()} the AI has ever flagged`
      ),
      statCard(
        "Total analyses run",
        stats.total_analyses.toLocaleString(),
        "Manual + live simulation analyses completed so far — not the same as human-reviewed"
      ),
    ].join("");

    if (stats.latest_evaluation && stats.latest_evaluation.status === "completed") {
      const ev = stats.latest_evaluation;
      accuracyBox.innerHTML = `
        <div class="ls-metric-box" title="How often the AI was right when it had similar past cases to compare against">
          <div class="ls-metric-label">AI accuracy (using evidence)</div>
          <div class="ls-metric-value ls-metric-grounded">${(ev.grounded_accuracy * 100).toFixed(0)}%</div>
          <div class="ls-metric-sub">RAG-grounded · based on ${ev.sample_size} tested cases · ${formatDate(ev.created_at)}</div>
        </div>
        <div class="ls-metric-box" title="How often the AI was right when guessing without any past cases to compare against">
          <div class="ls-metric-label">AI accuracy (guessing alone)</div>
          <div class="ls-metric-value ls-metric-ungrounded">${(ev.ungrounded_accuracy * 100).toFixed(0)}%</div>
          <div class="ls-metric-sub">Ungrounded · based on ${ev.sample_size} tested cases · ${formatDate(ev.created_at)}</div>
        </div>`;
    } else {
      accuracyBox.innerHTML = `<div class="ls-empty">No completed accuracy tests yet. <a href="evaluate.html">Run one</a>.</div>`;
    }

    return stats;
  } catch (err) {
    grid.innerHTML = `<div class="ls-empty">Failed to load stats: ${escapeHtml(err.message)}</div>`;
    return null;
  }
}

let topPriorityBlock = null;

async function loadBanner() {
  const el = document.getElementById("banner-text");
  const btn = document.getElementById("review-top-btn");
  try {
    const [stats, top] = await Promise.all([
      api.stats(),
      api.listBlocks({ predicted_label: "Anomaly", reviewed: false, sort: "confidence_desc", limit: 1 }),
    ]);
    topPriorityBlock = top[0] || null;

    if (topPriorityBlock) {
      const conf = (topPriorityBlock.predicted_confidence * 100).toFixed(0);
      el.innerHTML = `
        <b>${stats.flagged_unreviewed.toLocaleString()}</b> flagged case(s) still need a look —
        highest priority is <b>${escapeHtml(topPriorityBlock.block_id)}</b>
        <span class="ls-muted">(${conf}% confidence)</span>`;
      btn.disabled = false;
      btn.textContent = "Review block →";
    } else {
      el.innerHTML = `<b>Nothing pending.</b> <span class="ls-muted">Every flagged case has been reviewed.</span>`;
      btn.disabled = true;
      btn.textContent = "Nothing to review";
    }
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load: ${escapeHtml(err.message)}</div>`;
    btn.disabled = true;
  }
}

document.getElementById("review-top-btn").addEventListener("click", async () => {
  if (!topPriorityBlock) return;
  const btn = document.getElementById("review-top-btn");
  btn.disabled = true;
  btn.textContent = "Marking reviewed…";
  try {
    await api.reviewBlock(topPriorityBlock.block_id);
    window.location.href = `analyze.html?block=${encodeURIComponent(topPriorityBlock.block_id)}`;
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "Review block →";
    alert(`Couldn't mark this reviewed: ${err.message}`);
  }
});

document.getElementById("topbar-search").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const id = e.target.value.trim();
    if (id) window.location.href = `analyze.html?block=${encodeURIComponent(id)}`;
  }
});

async function loadBlockDetail(analysisId, blockId) {
  const panel = document.getElementById("block-detail-panel");
  panel.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading…</div>`;
  try {
    const a = await api.getAnalysis(analysisId);
    const evidenceHtml = a.evidence
      .slice(0, 3)
      .map(
        (e) => `
      <div class="ls-row" style="align-items: flex-start; gap: 0.5rem; padding: 0.4rem 0; border-bottom: 1px solid var(--border-light);">
        ${badgeHtml(e.label)}
        <span class="ls-muted" style="flex: 1;">${escapeHtml(e.block_id)}${e.score !== null ? ` · similarity ${e.score.toFixed(2)}` : ""}</span>
      </div>`
      )
      .join("");

    panel.innerHTML = `
      <div class="ls-row" style="justify-content: space-between; align-items: flex-start;">
        <div>
          <div style="font-weight: 600;">${escapeHtml(a.block_id)}</div>
          <div class="ls-row" style="margin-top: 0.3rem;">${badgeHtml(a.predicted_label)}<span class="ls-muted">${(a.confidence * 100).toFixed(0)}% confidence</span></div>
        </div>
        ${sourceTagHtml(a.source)}
      </div>
      <div class="ls-section-title" style="margin-top: 1rem;">AI explanation</div>
      <p class="ls-muted" style="margin: 0;">${escapeHtml(a.grounded_explanation)}</p>
      ${
        evidenceHtml
          ? `<div class="ls-section-title">Similar past incidents</div>${evidenceHtml}`
          : ""
      }
      <div style="margin-top: 1rem;">
        <a class="ls-btn ls-btn-ghost" href="analyze.html?block=${encodeURIComponent(blockId)}">Open full analysis →</a>
      </div>`;
  } catch (err) {
    panel.innerHTML = `<div class="ls-empty">Failed to load: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadRecentAnalyses() {
  const el = document.getElementById("recent-analyses");
  try {
    const analyses = await api.listAnalyses({ limit: 8 });
    if (analyses.length === 0) {
      el.innerHTML = `<div class="ls-empty">No analyses yet. <a href="analyze.html">Analyze a block</a> to get started.</div>`;
      return;
    }
    el.innerHTML = `
      <div class="ls-table-wrap">
        <table class="ls-table">
          <thead><tr><th>Block</th><th>Verdict</th><th title="How sure the AI is in this verdict">Confidence</th><th>When</th></tr></thead>
          <tbody>
            ${analyses
              .map(
                (a) => `
              <tr data-analysis-id="${a.id}" data-block-id="${escapeHtml(a.block_id)}">
                <td>${escapeHtml(a.block_id)} ${sourceTagHtml(a.source)}</td>
                <td>${badgeHtml(a.predicted_label)}</td>
                <td>${(a.confidence * 100).toFixed(0)}%</td>
                <td class="ls-muted">${formatDate(a.created_at)}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
    const rows = el.querySelectorAll("tbody tr");
    rows.forEach((row) => {
      row.addEventListener("click", () => {
        rows.forEach((r) => r.classList.remove("ls-row-selected"));
        row.classList.add("ls-row-selected");
        loadBlockDetail(row.dataset.analysisId, row.dataset.blockId);
      });
    });
    if (rows.length && document.getElementById("block-detail-panel").querySelector(".ls-empty")) {
      rows[0].click();
    }
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load recent analyses: ${escapeHtml(err.message)}</div>`;
  }
}

// Rolling window of real simulation ticks, built client-side from
// /api/simulation/status polling — no fabricated log noise, only genuine
// tick events this browser has actually observed.
const simLines = [];
let lastSeenTick = null;
let flaggedLiveCount = 0;

function renderTerminal() {
  const el = document.getElementById("sim-terminal");
  if (simLines.length === 0) {
    el.innerHTML = `<div class="ls-empty" style="color: var(--sidebar-text-muted); text-align: left; padding: 0;">Not running.</div>`;
    return;
  }
  el.innerHTML = simLines
    .map(
      (l) => `
    <div class="ls-terminal-line">
      <span class="ls-t-time">${l.time}</span>
      <span>${escapeHtml(l.blockId)} → <span style="color: ${l.verdict === "Anomaly" ? "var(--danger-strong)" : "var(--success-strong)"};">${l.verdict}</span></span>
    </div>`
    )
    .join("");
}

function simStatusLine(sim) {
  if (!sim.running) {
    if (sim.ticks > 0) {
      return `Stopped. Ran ${sim.ticks} block(s)${sim.errors ? `, ${sim.errors} error(s)` : ""} this session.`;
    }
    return "Not running.";
  }
  return `<span class="ls-spinner"></span> Running every ${sim.interval_seconds}s. ${sim.errors ? `${sim.errors} error(s) so far.` : ""}`;
}

async function loadSimulationStatus() {
  try {
    const sim = await api.simulationStatus();
    document.getElementById("sim-status").innerHTML = simStatusLine(sim);
    const toggle = document.getElementById("sim-toggle");
    toggle.setAttribute("aria-checked", sim.running ? "true" : "false");
    toggle.disabled = false;
    document.getElementById("sim-toggle-label").textContent = sim.running ? "On" : "Off";
    document.getElementById("sim-interval").disabled = sim.running;
    document.getElementById("sim-dot").style.background = sim.running ? "var(--success-strong)" : "var(--text-faint)";
    document.getElementById("sim-processed").textContent = sim.ticks.toLocaleString();

    if (sim.last_ran_at && sim.last_ran_at !== lastSeenTick) {
      lastSeenTick = sim.last_ran_at;
      simLines.push({
        time: new Date(sim.last_ran_at).toLocaleTimeString(),
        blockId: sim.last_block_id,
        verdict: sim.last_verdict,
      });
      if (sim.last_verdict === "Anomaly") flaggedLiveCount += 1;
      while (simLines.length > 8) simLines.shift();
      renderTerminal();
      document.getElementById("sim-flagged").textContent = flaggedLiveCount.toLocaleString();
    }
    return sim.running;
  } catch (err) {
    document.getElementById("sim-status").textContent = `Failed to load simulation status: ${err.message}`;
    return false;
  }
}

document.getElementById("sim-toggle").addEventListener("click", async (e) => {
  const toggle = e.currentTarget;
  const turningOn = toggle.getAttribute("aria-checked") !== "true";
  toggle.disabled = true;
  try {
    if (turningOn) {
      const interval = parseFloat(document.getElementById("sim-interval").value) || 20;
      await api.startSimulation(interval);
    } else {
      await api.stopSimulation();
    }
    await loadSimulationStatus();
  } catch (err) {
    document.getElementById("sim-status").textContent = `Failed to ${turningOn ? "start" : "stop"}: ${err.message}`;
    toggle.disabled = false;
  }
});

async function refreshAll() {
  const running = await loadSimulationStatus();
  await loadBanner();
  await loadStats();
  await loadRecentAnalyses();
  return running;
}

refreshAll();

// Keep the dashboard current on its own — that's the point of "live":
// poll a bit faster while the simulation is actually running, and settle
// into a slower background refresh otherwise.
setInterval(async () => {
  await loadSimulationStatus();
  await loadBanner();
  await loadStats();
}, 8000);
