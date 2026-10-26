const API_BASE = "/api";

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

const api = {
  stats: () => apiRequest("/stats"),
  listBlocks: (params = {}) => apiRequest(`/blocks?${new URLSearchParams(params)}`),
  getBlock: (blockId) => apiRequest(`/blocks/${encodeURIComponent(blockId)}`),
  reviewBlock: (blockId) =>
    apiRequest(`/blocks/${encodeURIComponent(blockId)}/review`, { method: "POST" }),
  analyzeBlock: (blockId, { includeUngrounded = true, topK = 3 } = {}) =>
    apiRequest(
      `/blocks/${encodeURIComponent(blockId)}/analyze?include_ungrounded=${includeUngrounded}&top_k=${topK}`,
      { method: "POST" }
    ),
  listAnalyses: (params = {}) => apiRequest(`/analyses?${new URLSearchParams(params)}`),
  getAnalysis: (id) => apiRequest(`/analyses/${id}`),
  getIncidentTicket: (id) => apiRequest(`/analyses/${id}/ticket`),
  createEvaluation: (sampleSize) =>
    apiRequest("/evaluations", {
      method: "POST",
      body: JSON.stringify({ sample_size: sampleSize }),
    }),
  listEvaluations: (params = {}) => apiRequest(`/evaluations?${new URLSearchParams(params)}`),
  getEvaluation: (id) => apiRequest(`/evaluations/${id}`),
  startSimulation: (intervalSeconds) =>
    apiRequest("/simulation/start", {
      method: "POST",
      body: JSON.stringify({ interval_seconds: intervalSeconds }),
    }),
  stopSimulation: () => apiRequest("/simulation/stop", { method: "POST" }),
  simulationStatus: () => apiRequest("/simulation/status"),
  timeline: (days) => apiRequest(`/reports/timeline?days=${days}`),
  eventPatterns: (limit = 8) => apiRequest(`/reports/event-patterns?limit=${limit}`),
  chat: (message, history) =>
    apiRequest("/chat", { method: "POST", body: JSON.stringify({ message, history }) }),
};

function severityHtml(confidence) {
  if (confidence === null || confidence === undefined) return "";
  let cls, text;
  if (confidence >= 0.99) {
    cls = "ls-badge-anomaly";
    text = "Highest";
  } else if (confidence >= 0.9) {
    cls = "ls-badge-anomaly";
    text = "High";
  } else {
    cls = "ls-badge-muted";
    text = "Moderate";
  }
  return `<span class="ls-badge ${cls}" title="Based on how confident the AI is in this verdict">${text} confidence</span>`;
}

function badgeHtml(label) {
  if (!label) return `<span class="ls-badge ls-badge-muted">Not yet checked</span>`;
  const cls = label === "Anomaly" ? "ls-badge-anomaly" : "ls-badge-normal";
  const title = label === "Anomaly" ? "The AI thinks this looks like a real problem" : "The AI thinks this looks normal";
  return `<span class="ls-badge ${cls}" title="${title}">${label}</span>`;
}

async function renderIncidentTicket(containerEl, analysisId) {
  containerEl.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Drafting incident ticket…</div>`;
  try {
    const ticket = await api.getIncidentTicket(analysisId);
    const fullText = `${ticket.title}\n\n${ticket.body}`;
    containerEl.innerHTML = `
      <div class="ls-card">
        <div class="ls-row" style="justify-content: space-between; align-items: center; flex-wrap: nowrap;">
          <b>${escapeHtml(ticket.title)}</b>
          <button class="ls-btn ls-btn-ghost" id="copy-ticket-btn-${analysisId}">Copy to clipboard</button>
        </div>
        <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.85rem; margin: 0.75rem 0 0;">${escapeHtml(ticket.body)}</pre>
      </div>`;
    const copyBtn = document.getElementById(`copy-ticket-btn-${analysisId}`);
    copyBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText(fullText);
        copyBtn.textContent = "Copied!";
      } catch (_) {
        copyBtn.textContent = "Couldn't copy — select manually";
      }
      setTimeout(() => (copyBtn.textContent = "Copy to clipboard"), 1500);
    };
  } catch (err) {
    containerEl.innerHTML = `<div class="ls-empty">Couldn't draft a ticket: ${escapeHtml(err.message)}</div>`;
  }
}

function sourceTagHtml(source) {
  if (source !== "simulation") return "";
  return `<span class="ls-badge ls-badge-muted" title="Generated automatically by Live Simulation, replaying a stored historical case through the live pipeline">Live</span>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// LLM output sometimes uses markdown bold ("**word**") for emphasis. We
// don't want to render markdown generally (that's an injection surface
// for anything beyond this one pattern), so escape first, then allow
// only this single, narrow pattern through as real <strong> tags —
// everything else stays as literal, safely-escaped text.
function formatLLMText(str) {
  return escapeHtml(str).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function confidenceHtml(block) {
  if (!block.has_analysis || block.predicted_confidence === null) {
    return `<span class="ls-muted">Not analyzed yet</span>`;
  }
  return `<span title="How sure the AI is in this verdict">${(block.predicted_confidence * 100).toFixed(0)}%</span>`;
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString();
}
