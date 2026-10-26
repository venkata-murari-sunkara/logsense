const PAGE_SIZE = 20;
let currentOffset = 0;
let selectedBlockId = null;

function currentFilters() {
  return {
    search: document.getElementById("search-input").value.trim(),
    label: document.getElementById("label-filter").value,
    predicted_label: document.getElementById("predicted-filter").value,
  };
}

async function loadBlocks(offset = 0) {
  currentOffset = offset;
  const listEl = document.getElementById("block-list");
  listEl.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading…</div>`;

  const filters = currentFilters();
  const params = { limit: PAGE_SIZE, offset };
  if (filters.search) params.search = filters.search;
  if (filters.label) params.label = filters.label;
  if (filters.predicted_label) params.predicted_label = filters.predicted_label;

  try {
    const blocks = await api.listBlocks(params);
    if (blocks.length === 0) {
      listEl.innerHTML = `<div class="ls-empty">No blocks match this filter.</div>`;
    } else {
      listEl.innerHTML = `
        <div class="ls-table-wrap">
          <table class="ls-table">
            <thead><tr><th>Block ID</th><th>Ground truth</th><th>Model verdict</th><th>Confidence</th></tr></thead>
            <tbody>
              ${blocks
                .map(
                  (b) => `
                <tr data-block-id="${escapeHtml(b.block_id)}">
                  <td>${escapeHtml(b.block_id)}</td>
                  <td>${badgeHtml(b.true_label)}</td>
                  <td>${badgeHtml(b.predicted_label)}</td>
                  <td>${confidenceHtml(b)}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;
      listEl.querySelectorAll("tbody tr").forEach((row) => {
        row.addEventListener("click", () => selectBlock(row.dataset.blockId));
      });
    }

    document.getElementById("pagination").innerHTML = `
      <button class="ls-btn ls-btn-ghost" id="prev-page" ${offset === 0 ? "disabled" : ""}>← Previous</button>
      <span class="ls-muted">Showing ${offset + 1}–${offset + blocks.length}</span>
      <button class="ls-btn ls-btn-ghost" id="next-page" ${blocks.length < PAGE_SIZE ? "disabled" : ""}>Next →</button>`;
    document.getElementById("prev-page").onclick = () => loadBlocks(Math.max(0, offset - PAGE_SIZE));
    document.getElementById("next-page").onclick = () => loadBlocks(offset + PAGE_SIZE);
  } catch (err) {
    listEl.innerHTML = `<div class="ls-empty">Failed to load blocks: ${escapeHtml(err.message)}</div>`;
  }
}

async function selectBlock(blockId, autoAnalyze = false) {
  selectedBlockId = blockId;
  const panel = document.getElementById("analysis-panel");
  panel.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading block ${escapeHtml(blockId)}…</div>`;
  window.scrollTo({ top: 0, behavior: "smooth" });

  try {
    const block = await api.getBlock(blockId);
    const conf = block.predicted_confidence !== null ? (block.predicted_confidence * 100).toFixed(1) + "%" : "—";
    panel.innerHTML = `
      <div class="ls-section-title">Selected block</div>
      ${autoAnalyze ? `<p class="ls-muted">Opened from Priorities — running the full analysis automatically…</p>` : ""}
      <div class="ls-card">
        <b>Block:</b> ${escapeHtml(block.block_id)}<br>
        <b>Model verdict:</b> ${badgeHtml(block.predicted_label)} (confidence: ${conf})<br><br>
        <b>Log history:</b><br>${escapeHtml(block.description)}
      </div>
      <div class="ls-row" style="margin: 1rem 0;">
        <label class="ls-muted"><input type="checkbox" id="include-ungrounded" checked /> Also generate an ungrounded explanation (for comparison)</label>
      </div>
      <button class="ls-btn" id="analyze-btn">Analyze block</button>
      <div id="analysis-result"></div>`;

    document.getElementById("analyze-btn").onclick = () => runAnalysis(blockId, block.true_label);

    if (autoAnalyze) {
      runAnalysis(blockId, block.true_label);
    }
  } catch (err) {
    panel.innerHTML = `<div class="ls-empty">Failed to load block: ${escapeHtml(err.message)}</div>`;
  }
}

async function runAnalysis(blockId, trueLabel) {
  const btn = document.getElementById("analyze-btn");
  const resultEl = document.getElementById("analysis-result");
  const includeUngrounded = document.getElementById("include-ungrounded").checked;

  btn.disabled = true;
  resultEl.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Running detection, retrieval, and explanation…</div>`;

  try {
    const result = await api.analyzeBlock(blockId, { includeUngrounded });

    const evidenceHtml = result.evidence
      .map(
        (e) => `
      <div class="ls-card">
        ${badgeHtml(e.label)} &nbsp; Block ${escapeHtml(e.block_id)}
        ${e.score !== null ? `<span class="ls-muted"> · similarity ${e.score.toFixed(3)}</span>` : ""}
        <br><br>${escapeHtml(e.description)}
      </div>`
      )
      .join("");

    resultEl.innerHTML = `
      <div class="ls-grid ls-grid-2">
        <div>
          <div class="ls-section-title">System verdict</div>
          <div class="ls-card">
            ${badgeHtml(result.predicted_label)} &nbsp; confidence: ${(result.confidence * 100).toFixed(0)}%
          </div>
        </div>
        <div>
          <div class="ls-section-title">Similar past incidents (evidence)</div>
          ${evidenceHtml || '<div class="ls-empty">No evidence retrieved.</div>'}
        </div>
      </div>

      <div class="ls-section-title">AI explanation, grounded in evidence (RAG)</div>
      <div class="ls-card-accent">${formatLLMText(result.grounded_explanation)}</div>

      ${
        result.recommendation
          ? `<div class="ls-section-title">What to do about it</div>
             <div class="ls-card" style="white-space: pre-line; border-left: 4px solid var(--success);">${formatLLMText(result.recommendation)}</div>`
          : ""
      }

      ${
        result.ungrounded_explanation
          ? `<div class="ls-section-title">AI explanation, without evidence (baseline)</div>
             <div class="ls-card">${formatLLMText(result.ungrounded_explanation)}</div>`
          : ""
      }

      ${
        result.predicted_label === "Anomaly"
          ? `<div class="ls-section-title">Incident ticket (auto-drafted)</div>
             <div id="ticket-container-${result.id}"></div>`
          : ""
      }

      <hr>
      <p><b>Ground truth label (for verification):</b> ${badgeHtml(trueLabel)}</p>`;

    if (result.predicted_label === "Anomaly") {
      renderIncidentTicket(document.getElementById(`ticket-container-${result.id}`), result.id);
    }
  } catch (err) {
    resultEl.innerHTML = `<div class="ls-empty">Analysis failed: ${escapeHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("search-btn").onclick = () => loadBlocks(0);
document.getElementById("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadBlocks(0);
});
document.getElementById("label-filter").onchange = () => loadBlocks(0);
document.getElementById("predicted-filter").onchange = () => loadBlocks(0);

loadBlocks(0);

try {
  const deepLinkBlockId = new URLSearchParams(window.location.search).get("block");
  if (deepLinkBlockId) {
    selectBlock(deepLinkBlockId, true);
  } else {
    document.getElementById("analysis-panel").innerHTML =
      `<div class="ls-empty">Pick a block below, or open one from <a href="priorities.html">Case Priorities</a>, to see its analysis here.</div>`;
  }
} catch (err) {
  const panel = document.getElementById("analysis-panel");
  if (panel) panel.innerHTML = `<div class="ls-empty">Couldn't open the linked block: ${escapeHtml(err.message)}</div>`;
}
