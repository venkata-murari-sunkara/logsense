const PAGE_SIZE = 25;

async function loadDetail(id) {
  const el = document.getElementById("analysis-detail");
  el.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading analysis #${id}…</div>`;
  try {
    const a = await api.getAnalysis(id);
    const evidenceHtml = a.evidence
      .map(
        (e) => `
      <div class="ls-card">
        ${badgeHtml(e.label)} &nbsp; Block ${escapeHtml(e.block_id)}
        ${e.score !== null ? `<span class="ls-muted"> · similarity ${e.score.toFixed(3)}</span>` : ""}
        <br><br>${escapeHtml(e.description)}
      </div>`
      )
      .join("");

    el.innerHTML = `
      <div class="ls-section-title">Analysis #${a.id} — block ${escapeHtml(a.block_id)} ${sourceTagHtml(a.source)}</div>
      <div class="ls-grid ls-grid-2">
        <div class="ls-card">
          <b>System verdict:</b> ${badgeHtml(a.predicted_label)} (confidence ${(a.confidence * 100).toFixed(0)}%)<br>
          <b>Ground truth:</b> ${badgeHtml(a.true_label)}<br>
          <b>Run at:</b> ${formatDate(a.created_at)}<br>
          <b>Reviewed:</b> ${a.reviewed_at ? `<span class="ls-badge ls-badge-muted">Reviewed ${formatDate(a.reviewed_at)}</span>` : '<span class="ls-muted">Not yet reviewed</span>'}
        </div>
        <div>${evidenceHtml}</div>
      </div>
      <div class="ls-card-accent"><b>Grounded explanation:</b><br>${escapeHtml(a.grounded_explanation)}</div>
      ${
        a.recommendation
          ? `<div class="ls-card" style="white-space: pre-line; border-left: 4px solid var(--success);"><b>What to do about it:</b><br>${escapeHtml(a.recommendation)}</div>`
          : ""
      }
      ${
        a.ungrounded_explanation
          ? `<div class="ls-card"><b>Ungrounded explanation:</b><br>${escapeHtml(a.ungrounded_explanation)}</div>`
          : ""
      }
      ${
        a.predicted_label === "Anomaly"
          ? `<div class="ls-section-title">Incident ticket (auto-drafted)</div>
             <div id="ticket-container-${a.id}"></div>`
          : ""
      }
      <hr>`;

    if (a.predicted_label === "Anomaly") {
      renderIncidentTicket(document.getElementById(`ticket-container-${a.id}`), a.id);
    }
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load analysis: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadHistory(offset = 0) {
  const listEl = document.getElementById("history-list");
  listEl.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading…</div>`;

  const verdict = document.getElementById("verdict-filter").value;
  const reviewed = document.getElementById("reviewed-filter").value;
  const params = { limit: PAGE_SIZE, offset };
  if (verdict) params.predicted_label = verdict;
  if (reviewed) params.reviewed = reviewed;

  try {
    const analyses = await api.listAnalyses(params);
    if (analyses.length === 0) {
      listEl.innerHTML = verdict || reviewed
        ? `<div class="ls-empty">No analyses match this filter.</div>`
        : `<div class="ls-empty">No analyses yet. <a href="analyze.html">Analyze a block</a> to get started.</div>`;
    } else {
      listEl.innerHTML = `
        <div class="ls-table-wrap">
          <table class="ls-table">
            <thead><tr><th>#</th><th>Block</th><th>Verdict</th><th title="How sure the AI is in this verdict">Confidence</th><th>When</th><th>Reviewed?</th></tr></thead>
            <tbody>
              ${analyses
                .map(
                  (a) => `
                <tr data-id="${a.id}">
                  <td>${a.id}</td>
                  <td>${escapeHtml(a.block_id)} ${sourceTagHtml(a.source)}</td>
                  <td>${badgeHtml(a.predicted_label)}</td>
                  <td>${(a.confidence * 100).toFixed(0)}%</td>
                  <td class="ls-muted">${formatDate(a.created_at)}</td>
                  <td>${a.reviewed_at ? `<span class="ls-badge ls-badge-muted" title="Reviewed ${formatDate(a.reviewed_at)}">Reviewed</span>` : '<span class="ls-muted">Not yet</span>'}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;
      listEl.querySelectorAll("tbody tr").forEach((row) => {
        row.addEventListener("click", () => {
          const id = row.dataset.id;
          history.replaceState(null, "", `history.html?id=${id}`);
          loadDetail(id);
          document.getElementById("analysis-detail").scrollIntoView({ behavior: "smooth" });
        });
      });
    }

    document.getElementById("pagination").innerHTML = `
      <button class="ls-btn ls-btn-ghost" id="prev-page" ${offset === 0 ? "disabled" : ""}>← Previous</button>
      <span class="ls-muted">Showing ${offset + 1}–${offset + analyses.length}</span>
      <button class="ls-btn ls-btn-ghost" id="next-page" ${analyses.length < PAGE_SIZE ? "disabled" : ""}>Next →</button>`;
    document.getElementById("prev-page").onclick = () => loadHistory(Math.max(0, offset - PAGE_SIZE));
    document.getElementById("next-page").onclick = () => loadHistory(offset + PAGE_SIZE);
  } catch (err) {
    listEl.innerHTML = `<div class="ls-empty">Failed to load history: ${escapeHtml(err.message)}</div>`;
  }
}

document.getElementById("verdict-filter").addEventListener("change", () => loadHistory(0));
document.getElementById("reviewed-filter").addEventListener("change", () => loadHistory(0));

const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get("id")) {
  loadDetail(urlParams.get("id"));
}
loadHistory(0);
