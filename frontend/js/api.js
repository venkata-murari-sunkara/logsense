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
    let approved = false;
    let severity = ticket.severity;

    const statusText = () =>
      approved ? "Awaiting human triage" : "Potential anomaly — awaiting human triage";

    const fullText = () =>
      `${ticket.title}\n\nStatus: ${statusText()}\nConfidence: ${(ticket.confidence * 100).toFixed(1)}%\nSeverity: ${severity}\n\n${ticket.body}`;

    const render = () => {
      containerEl.innerHTML = `
        <div class="ls-card">
          <div class="ls-row" style="justify-content: space-between; align-items: center; flex-wrap: nowrap;">
            <b>${escapeHtml(ticket.title)}</b>
            <div class="ls-row" style="gap: 0.4rem;">
              <button class="ls-btn ls-btn-ghost" id="approve-ticket-btn-${analysisId}" ${approved ? "disabled" : ""}>${approved ? "Approved ✓" : "Approve"}</button>
              <button class="ls-btn ls-btn-ghost" id="copy-ticket-btn-${analysisId}">Copy to clipboard</button>
            </div>
          </div>
          <p class="ls-muted" style="margin: 0.5rem 0 0;">Status: ${statusText()}</p>
          <div class="ls-row" style="gap: 1.5rem; margin: 0.5rem 0 0;">
            <span class="ls-muted" title="How sure the AI is in this verdict">Confidence: <b>${(ticket.confidence * 100).toFixed(1)}%</b></span>
            <label class="ls-muted" title="How serious the problem looks — starts from a simple rule, change it if you know better">
              Severity:
              <select id="severity-select-${analysisId}">
                ${["Low", "Medium", "High"].map((s) => `<option value="${s}" ${s === severity ? "selected" : ""}>${s}</option>`).join("")}
              </select>
            </label>
          </div>
          <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.85rem; margin: 0.75rem 0 0;">${formatLLMText(ticket.body)}</pre>
        </div>`;

      document.getElementById(`severity-select-${analysisId}`).addEventListener("change", (e) => {
        severity = e.target.value;
      });
      document.getElementById(`approve-ticket-btn-${analysisId}`).addEventListener("click", () => {
        approved = true;
        render();
      });
      const copyBtn = document.getElementById(`copy-ticket-btn-${analysisId}`);
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(fullText());
          copyBtn.textContent = "Copied!";
        } catch (_) {
          copyBtn.textContent = "Couldn't copy — select manually";
        }
        setTimeout(() => (copyBtn.textContent = "Copy to clipboard"), 1500);
      };
    };

    render();
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
