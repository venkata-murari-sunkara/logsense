let pollTimer = null;
let stoppingRunId = null;
let currentRunId = null;
let currentDetailRunId = null;
const MIN_RELIABLE_SAMPLE = 20;

function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function statusLine(run) {
  const total = run.sample_size;
  const done = run.results ? run.results.length : null;

  if (run.status === "running") {
    if (stoppingRunId === run.id) {
      return `Stopping… (already-in-progress cases are finishing, nothing new will start)`;
    }
    const elapsed = formatDuration(Date.now() - new Date(run.created_at).getTime());
    const progress = done !== null ? `${done} of ${total} done · ${total - done} remaining · ` : "";
    return `<span class="ls-spinner"></span> Run #${run.id}: ${progress}Elapsed ${elapsed}`;
  }

  const duration = run.completed_at
    ? formatDuration(new Date(run.completed_at).getTime() - new Date(run.created_at).getTime())
    : "";

  if (run.status === "stopped") {
    const attempted = done !== null ? done + (run.failed_count || 0) : total;
    return `Stopped at ${attempted} of ${total} · ran for ${duration}`;
  }

  if (run.status === "failed") {
    return `Run #${run.id} failed after ${duration}.`;
  }

  // completed
  const effectiveN = total - (run.failed_count || 0);
  const caveat =
    effectiveN < MIN_RELIABLE_SAMPLE
      ? ` ⚠️ n=${effectiveN} is too small to be statistically meaningful — treat this as noise, not a real result.`
      : "";
  const failedNote = run.failed_count > 0 ? ` (${run.failed_count} block(s) failed and were skipped)` : "";
  return `Finished ${total} cases in ${duration}: grounded ${(run.grounded_accuracy * 100).toFixed(0)}% vs ungrounded ${(run.ungrounded_accuracy * 100).toFixed(0)}% on n=${effectiveN}.${failedNote}${caveat}`;
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
  currentRunId = id;
  const statusEl = document.getElementById("run-status");
  const stopBtn = document.getElementById("stop-btn");
  document.getElementById("run-btn").disabled = true;

  const tick = async () => {
    try {
      const run = await api.getEvaluation(id);
      statusEl.innerHTML = statusLine(run);
      if (run.status === "running") {
        stopBtn.hidden = false;
        stopBtn.disabled = stoppingRunId === run.id;
        stopBtn.textContent = stoppingRunId === run.id ? "Stopping…" : "Stop";
      } else {
        clearInterval(pollTimer);
        stoppingRunId = null;
        stopBtn.hidden = true;
        document.getElementById("run-btn").disabled = false;
        loadRuns();
        if (currentDetailRunId === String(id)) loadRunDetail(id, { scroll: false });
      }
    } catch (err) {
      statusEl.textContent = `Failed to poll run: ${err.message}`;
      clearInterval(pollTimer);
      stopBtn.hidden = true;
      document.getElementById("run-btn").disabled = false;
    }
  };
  await tick();
  pollTimer = setInterval(tick, 2500);
}

async function stopRun(id) {
  stoppingRunId = id;
  const stopBtn = document.getElementById("stop-btn");
  stopBtn.disabled = true;
  stopBtn.textContent = "Stopping…";
  try {
    await api.stopEvaluation(id);
  } catch (err) {
    stoppingRunId = null;
    document.getElementById("run-status").textContent = `Failed to stop run: ${err.message}`;
    stopBtn.disabled = false;
    stopBtn.textContent = "Stop";
  }
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

function statusLabelHtml(status) {
  if (status === "stopped") {
    return `<span title="Stopped before all cases finished — excluded from dashboard accuracy totals">Stopped (partial)</span>`;
  }
  return escapeHtml(status);
}

let lastRuns = [];

function renderRuns() {
  const listEl = document.getElementById("run-list");
  const hideFailed = document.getElementById("hide-failed-runs").checked;
  const runs = hideFailed ? lastRuns.filter((r) => r.status !== "failed") : lastRuns;

  if (lastRuns.length === 0) {
    listEl.innerHTML = `<div class="ls-empty">No evaluation runs yet.</div>`;
    return;
  }
  if (runs.length === 0) {
    listEl.innerHTML = `<div class="ls-empty">No runs to show — every run so far has failed.</div>`;
    return;
  }
  listEl.innerHTML = `
      <div class="ls-table-wrap">
        <table class="ls-table">
          <thead><tr><th>#</th><th>Sample size</th><th>Status</th><th>Grounded</th><th>Ungrounded</th><th>Duration</th><th>When</th><th></th></tr></thead>
          <tbody>
            ${runs
              .map(
                (r) => `
              <tr data-id="${r.id}">
                <td>${r.id}</td>
                <td>${r.sample_size}${r.failed_count > 0 ? ` <span class="ls-muted" title="${r.failed_count} block(s) failed and were skipped">(${r.failed_count} failed)</span>` : ""}${r.sample_size - (r.failed_count || 0) < MIN_RELIABLE_SAMPLE ? ' <span title="Sample too small to be statistically meaningful">⚠️</span>' : ""}</td>
                <td>${statusLabelHtml(r.status)}</td>
                <td>${r.grounded_accuracy !== null ? (r.grounded_accuracy * 100).toFixed(0) + "%" : "—"}</td>
                <td>${r.ungrounded_accuracy !== null ? (r.ungrounded_accuracy * 100).toFixed(0) + "%" : "—"}</td>
                <td class="ls-muted">${r.completed_at ? formatDuration(new Date(r.completed_at) - new Date(r.created_at)) : "—"}</td>
                <td class="ls-muted">${formatDate(r.created_at)}</td>
                <td>${
                  r.status === "running"
                    ? ""
                    : `<button type="button" class="ls-btn ls-btn-ghost delete-run-btn" data-id="${r.id}" title="Delete this run">Delete</button>`
                }</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
    listEl.querySelectorAll("tbody tr").forEach((row) => {
      row.addEventListener("click", () => loadRunDetail(row.dataset.id));
    });
    listEl.querySelectorAll(".delete-run-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteRun(btn.dataset.id);
      });
    });
}

async function deleteRun(id) {
  if (!confirm(`Delete run #${id}? This can't be undone.`)) return;
  try {
    await api.deleteEvaluation(id);
    lastRuns = lastRuns.filter((r) => String(r.id) !== String(id));
    renderRuns();
    if (currentDetailRunId === String(id)) {
      currentDetailRunId = null;
      document.getElementById("run-detail").innerHTML = "";
    }
  } catch (err) {
    alert(`Couldn't delete run #${id}: ${err.message}`);
  }
}

async function loadRuns() {
  const listEl = document.getElementById("run-list");
  try {
    lastRuns = await api.listEvaluations({ limit: 20 });
    renderRuns();
  } catch (err) {
    listEl.innerHTML = `<div class="ls-empty">Failed to load runs: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadRunDetail(id, { scroll = true } = {}) {
  currentDetailRunId = String(id);
  const el = document.getElementById("run-detail");
  el.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading run #${id}…</div>`;
  if (scroll) el.scrollIntoView({ behavior: "smooth" });
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
    const succeeded = run.results.length;
    const duration = run.completed_at
      ? formatDuration(new Date(run.completed_at) - new Date(run.created_at))
      : "—";
    el.innerHTML = `
      <div class="ls-section-title">Run #${run.id} detail ${run.status === "stopped" ? "— Stopped (partial)" : ""}</div>
      <div class="ls-card">
        Requested n=${run.sample_size} &nbsp;·&nbsp;
        <span class="${run.failed_count > 0 ? "" : "ls-muted"}">${succeeded} succeeded, ${run.failed_count || 0} failed and excluded</span>
        &nbsp;·&nbsp; grounded ${run.grounded_accuracy !== null ? (run.grounded_accuracy * 100).toFixed(1) + "%" : "—"}
        vs ungrounded ${run.ungrounded_accuracy !== null ? (run.ungrounded_accuracy * 100).toFixed(1) + "%" : "—"}
        <span class="ls-muted">(accuracy computed only over the ${succeeded} succeeded blocks)</span>
        &nbsp;·&nbsp; ran for ${duration}
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
document.getElementById("stop-btn").onclick = () => {
  if (currentRunId !== null) stopRun(currentRunId);
};
document.getElementById("sample-size").addEventListener("input", updateSampleSizeWarning);
updateSampleSizeWarning();
document.getElementById("hide-failed-runs").addEventListener("change", renderRuns);

// If a run is already in progress (e.g. the page was refreshed mid-run),
// resume live tracking instead of just showing it in the static history
// list — status is never lost on the backend, this just restores the
// frontend's view of it.
(async () => {
  await loadRuns();
  try {
    const runs = await api.listEvaluations({ limit: 1 });
    if (runs.length > 0 && runs[0].status === "running") {
      pollRun(runs[0].id);
    }
  } catch (_) {
    /* non-fatal — the history list already loaded */
  }
})();
