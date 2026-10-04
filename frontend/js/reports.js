let currentDays = 30;

function shortDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

async function loadAccuracyChart(days) {
  const el = document.getElementById("accuracy-chart");
  try {
    const runs = await api.listEvaluations({ limit: 100 });
    const cutoff = Date.now() - days * 86400000;
    const completed = runs
      .filter((r) => r.status === "completed" && new Date(r.created_at).getTime() >= cutoff)
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

    if (completed.length === 0) {
      el.innerHTML = `<div class="ls-empty">No accuracy tests in this range yet. <a href="evaluate.html">Run one</a>.</div>`;
      return;
    }

    const grounded = completed.map((r) => ({ x: r.id, y: r.grounded_accuracy, label: shortDate(r.created_at) }));
    const ungrounded = completed.map((r) => ({ x: r.id, y: r.ungrounded_accuracy, label: shortDate(r.created_at) }));

    renderAccuracyLineChart(el, [
      { name: "Using evidence (grounded)", color: "var(--primary-dark)", points: grounded },
      { name: "Guessing alone (ungrounded)", color: "var(--danger-text)", points: ungrounded },
    ]);
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load accuracy history: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadActivityChart(days) {
  const el = document.getElementById("activity-chart");
  try {
    const data = await api.timeline(days);
    renderActivityBarChart(el, data.days);
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load activity: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadPatternsChart() {
  const el = document.getElementById("patterns-chart");
  try {
    const data = await api.eventPatterns(8);
    const items = data.patterns
      .filter((p) => p.anomaly_rate > p.normal_rate)
      .map((p) => ({
        label: p.event_code,
        sublabel: `${escapeHtml(p.description)} — vs ${(p.normal_rate * 100).toFixed(1)}% of normal blocks`,
        value: p.anomaly_rate,
      }));
    renderMagnitudeBarChart(el, items);
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load event patterns: ${escapeHtml(err.message)}</div>`;
  }
}

function loadAll(days) {
  loadAccuracyChart(days);
  loadActivityChart(days);
  loadPatternsChart();
}

document.querySelectorAll("#date-range button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#date-range button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentDays = parseInt(btn.dataset.days, 10);
    loadAll(currentDays);
  });
});

loadAll(currentDays);
