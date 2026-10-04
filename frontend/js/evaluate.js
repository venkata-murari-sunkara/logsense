let pollTimer = null;
const MIN_RELIABLE_SAMPLE = 20;

function statusLine(run) {
  if (run.status === "running") {
    return `<span class="ls-spinner"></span> Run #${run.id} in progress (n=${run.sample_size})… this calls the LLM ${run.sample_size * 2} times, so it can take a few minutes.`;
  }
  if (run.status === "failed") {
    return `Run #${run.id} failed.`;
  }
  const effectiveN = run.sample_size - (run.failed_count || 0);
  const caveat =
    effectiveN < MIN_RELIABLE_SAMPLE
      ? ` ⚠️ n=${effectiveN} is too small to be statistically meaningful — treat this as noise, not a real result.`
      : "";
  const failedNote = run.failed_count > 0 ? ` (${run.failed_count} block(s) failed and were skipped)` : "";
  return `Run #${run.id} completed: grounded ${(run.grounded_accuracy * 100).toFixed(0)}% vs ungrounded ${(run.ungrounded_accuracy * 100).toFixed(0)}% on n=${effectiveN}.${failedNote}${caveat}`;
}

function updateSampleSizeWarning() {
  const sampleSize = parseInt(document.getElementById("sample-size").value, 10) || 0;
  const warningEl = document.getElementById("sample-size-warning");
  if (sampleSize > 0 && sampleSize < MIN_RELIABLE_SAMPLE) {
    warningEl.textContent = `⚠️ n=${sampleSize} is too small to trust — small samples can easily flip the comparison by chance. Use at least ${MIN_RELIABLE_SAMPLE}, ideally 100+.`;
    warningEl.hidden = false;
  } else {
    warningEl.hidden = true;
  }
}

async function pollRun(id) {
  clearInterval(pollTimer);
  const statusEl = document.getElementById("run-status");
  const tick = async () => {
    try {
      const run = await api.getEvaluation(id);
      statusEl.innerHTML = statusLine(run);
      if (run.status !== "running") {
        clearInterval(pollTimer);
        document.getElementById("run-btn").disabled = false;
        loadRuns();
      }
    } catch (err) {
      statusEl.textContent = `Failed to poll run: ${err.message}`;
      clearInterval(pollTimer);
      document.getElementById("run-btn").disabled = false;
    }
  };
  await tick();
  pollTimer = setInterval(tick, 2500);
}

async function runEvaluation() {
  const btn = document.getElementById("run-btn");
  const sampleSize = parseInt(document.getElementById("sample-size").value, 10) || 20;
  btn.disabled = true;
  document.getElementById("run-status").innerHTML = `<span class="ls-spinner"></span> Starting run…`;
  try {
    const run = await api.createEvaluation(sampleSize);
    loadRuns();
    pollRun(run.id);
  } catch (err) {
    document.getElementById("run-status").textContent = `Failed to start run: ${err.message}`;
    btn.disabled = false;
  }
}

async function loadRuns() {
  const listEl = document.getElementById("run-list");
  try {
    const runs = await api.listEvaluations({ limit: 20 });
    if (runs.length === 0) {
      listEl.innerHTML = `<div class="ls-empty">No evaluation runs yet.</div>`;
      return;
    }
    listEl.innerHTML = `
      <div class="ls-table-wrap">
        <table class="ls-table">
          <thead><tr><th>#</th><th>Sample size</th><th>Status</th><th>Grounded</th><th>Ungrounded</th><th>When</th></tr></thead>
          <tbody>
            ${runs
              .map(
                (r) => `
              <tr data-id="${r.id}">
                <td>${r.id}</td>
                <td>${r.sample_size}${r.failed_count > 0 ? ` <span class="ls-muted" title="${r.failed_count} block(s) failed and were skipped">(${r.failed_count} failed)</span>` : ""}${r.sample_size - (r.failed_count || 0) < MIN_RELIABLE_SAMPLE ? ' <span title="Sample too small to be statistically meaningful">⚠️</span>' : ""}</td>
                <td>${escapeHtml(r.status)}</td>
                <td>${r.grounded_accuracy !== null ? (r.grounded_accuracy * 100).toFixed(0) + "%" : "—"}</td>
                <td>${r.ungrounded_accuracy !== null ? (r.ungrounded_accuracy * 100).toFixed(0) + "%" : "—"}</td>
                <td class="ls-muted">${formatDate(r.created_at)}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
    listEl.querySelectorAll("tbody tr").forEach((row) => {
      row.addEventListener("click", () => loadRunDetail(row.dataset.id));
    });
  } catch (err) {
    listEl.innerHTML = `<div class="ls-empty">Failed to load runs: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadRunDetail(id) {
  const el = document.getElementById("run-detail");
  el.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading run #${id}…</div>`;
  el.scrollIntoView({ behavior: "smooth" });
  try {
    const run = await api.getEvaluation(id);
    const rowsHtml = run.results
      .map(
        (r) => `
      <tr>
        <td>${escapeHtml(r.block_id)}</td>
        <td>${badgeHtml(r.true_label)}</td>
        <td>${badgeHtml(r.grounded_verdict)} ${r.grounded_correct ? "✓" : "✗"}</td>
        <td>${badgeHtml(r.ungrounded_verdict)} ${r.ungrounded_correct ? "✓" : "✗"}</td>
      </tr>`
      )
      .join("");
    const succeeded = run.sample_size - (run.failed_count || 0);
    el.innerHTML = `
      <div class="ls-section-title">Run #${run.id} detail</div>
      <div class="ls-card">
        Requested n=${run.sample_size} &nbsp;·&nbsp;
        <span class="${run.failed_count > 0 ? "" : "ls-muted"}">${succeeded} succeeded, ${run.failed_count || 0} failed and excluded</span>
        &nbsp;·&nbsp; grounded ${run.grounded_accuracy !== null ? (run.grounded_accuracy * 100).toFixed(1) + "%" : "—"}
        vs ungrounded ${run.ungrounded_accuracy !== null ? (run.ungrounded_accuracy * 100).toFixed(1) + "%" : "—"}
        <span class="ls-muted">(accuracy computed only over the ${succeeded} succeeded blocks)</span>
      </div>
      <div class="ls-table-wrap">
        <table class="ls-table">
          <thead><tr><th>Block</th><th title="What actually happened, confirmed from historical records">True label</th><th title="AI's verdict when given similar past cases as evidence">Grounded verdict</th><th title="AI's verdict when guessing with no evidence">Ungrounded verdict</th></tr></thead>
          <tbody>${rowsHtml || `<tr><td colspan="4" class="ls-empty">No results yet.</td></tr>`}</tbody>
        </table>
      </div>`;
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load run detail: ${escapeHtml(err.message)}</div>`;
  }
}

document.getElementById("run-btn").onclick = runEvaluation;
document.getElementById("sample-size").addEventListener("input", updateSampleSizeWarning);
updateSampleSizeWarning();
loadRuns();
