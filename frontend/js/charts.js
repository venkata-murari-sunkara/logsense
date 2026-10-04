/*
 * Minimal, dependency-free SVG chart helpers.
 * Marks: 2px lines, >=8px end-dots with a 2px surface ring, 4px rounded
 * bar caps, hairline recessive gridlines, 2px surface gaps between
 * touching/stacked bars. One shared tooltip element, positioned per-chart.
 */

function _ensureTooltip() {
  let el = document.getElementById("ls-chart-tooltip");
  if (!el) {
    el = document.createElement("div");
    el.id = "ls-chart-tooltip";
    el.className = "ls-chart-tooltip";
    document.body.appendChild(el);
  }
  return el;
}

function _showTooltip(evt, html) {
  const el = _ensureTooltip();
  el.innerHTML = html;
  el.classList.add("visible");
  const pad = 14;
  el.style.left = `${evt.clientX + pad + window.scrollX}px`;
  el.style.top = `${evt.clientY + pad + window.scrollY}px`;
}

function _hideTooltip() {
  const el = document.getElementById("ls-chart-tooltip");
  if (el) el.classList.remove("visible");
}

function _niceMax(value) {
  if (value <= 0) return 1;
  const pow = Math.pow(10, Math.floor(Math.log10(value)));
  const n = value / pow;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * pow;
}

/**
 * Line chart, 1-3 series. series = [{name, color, points: [{x, y, label}]}]
 * y is expected 0-1 (rendered as a percentage axis).
 */
function renderAccuracyLineChart(container, series) {
  const W = 640, H = 260;
  const marginLeft = 42, marginRight = 16, marginTop = 16, marginBottom = 36;
  const plotW = W - marginLeft - marginRight;
  const plotH = H - marginTop - marginBottom;

  const allPoints = series.flatMap((s) => s.points);
  if (allPoints.length === 0) {
    container.innerHTML = `<div class="ls-empty">Not enough data yet.</div>`;
    return;
  }
  const n = allPoints.length / series.length;
  const xFor = (i) => marginLeft + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const yFor = (v) => marginTop + plotH - v * plotH;

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(
    (v) => `
    <line class="ls-chart-gridline" x1="${marginLeft}" x2="${W - marginRight}" y1="${yFor(v)}" y2="${yFor(v)}" />
    <text class="ls-chart-axis-text" x="${marginLeft - 8}" y="${yFor(v) + 3}" text-anchor="end">${Math.round(v * 100)}%</text>`
  ).join("");

  const xLabels = series[0].points
    .map((p, i) => {
      if (n > 8 && i % Math.ceil(n / 6) !== 0 && i !== n - 1) return "";
      return `<text class="ls-chart-axis-text" x="${xFor(i)}" y="${H - marginBottom + 16}" text-anchor="middle">${p.label}</text>`;
    })
    .join("");

  const seriesSvg = series
    .map((s) => {
      const path = s.points.map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(p.y)}`).join(" ");
      const last = s.points[s.points.length - 1];
      const dots = s.points
        .map(
          (p, i) => `
        <circle cx="${xFor(i)}" cy="${yFor(p.y)}" r="4" style="fill:${s.color};stroke:var(--surface)" stroke-width="2"
                class="ls-chart-hit" data-series="${escapeHtml(s.name)}" data-value="${(p.y * 100).toFixed(1)}" data-label="${escapeHtml(p.label)}" />`
        )
        .join("");
      return `
        <path d="${path}" fill="none" style="stroke:${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
        <text x="${xFor(n - 1) + 6}" y="${yFor(last.y) + 4}" font-size="11" style="fill:${s.color}" font-weight="600">${(last.y * 100).toFixed(0)}%</text>
        ${dots}`;
    })
    .join("");

  const legend = series
    .map(
      (s) => `
      <span class="ls-chart-legend-item">
        <span class="ls-chart-legend-swatch" style="background:${s.color}"></span>${escapeHtml(s.name)}
      </span>`
    )
    .join("");

  container.innerHTML = `
    <div class="ls-chart-legend">${legend}</div>
    <svg class="ls-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      ${gridLines}
      ${xLabels}
      ${seriesSvg}
    </svg>`;

  container.querySelectorAll(".ls-chart-hit").forEach((dot) => {
    dot.addEventListener("pointermove", (evt) => {
      _showTooltip(evt, `<b>${dot.dataset.value}%</b> — ${dot.dataset.series}<br>${dot.dataset.label}`);
    });
    dot.addEventListener("pointerleave", _hideTooltip);
  });
}

/**
 * Stacked bar chart. days = [{date, anomaly_count, normal_count}]
 */
function renderActivityBarChart(container, days) {
  if (days.length === 0) {
    container.innerHTML = `<div class="ls-empty">No activity in this range yet.</div>`;
    return;
  }
  const W = 640, H = 260;
  const marginLeft = 42, marginRight = 16, marginTop = 16, marginBottom = 36;
  const plotW = W - marginLeft - marginRight;
  const plotH = H - marginTop - marginBottom;

  const maxTotal = _niceMax(Math.max(...days.map((d) => d.anomaly_count + d.normal_count)));
  const n = days.length;
  const slot = plotW / n;
  const barW = Math.min(24, slot * 0.6);
  const gap = 2;

  const yFor = (v) => marginTop + plotH - (v / maxTotal) * plotH;
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(
    (f) => `
    <line class="ls-chart-gridline" x1="${marginLeft}" x2="${W - marginRight}" y1="${yFor(f * maxTotal)}" y2="${yFor(f * maxTotal)}" />
    <text class="ls-chart-axis-text" x="${marginLeft - 8}" y="${yFor(f * maxTotal) + 3}" text-anchor="end">${Math.round(f * maxTotal)}</text>`
  ).join("");

  const bars = days
    .map((d, i) => {
      const cx = marginLeft + slot * i + slot / 2;
      const x = cx - barW / 2;
      const normalH = (d.normal_count / maxTotal) * plotH;
      const anomalyH = (d.anomaly_count / maxTotal) * plotH;
      const baseY = marginTop + plotH;
      const normalY = baseY - normalH;
      const anomalyY = normalY - gap - anomalyH;
      const label = `<text class="ls-chart-axis-text" x="${cx}" y="${H - marginBottom + 16}" text-anchor="middle">${d.date.slice(5)}</text>`;
      const normalRect =
        d.normal_count > 0
          ? `<rect class="ls-chart-bar" x="${x}" y="${normalY}" width="${barW}" height="${normalH}" rx="0" style="fill:var(--normal-text)"
               data-date="${d.date}" data-normal="${d.normal_count}" data-anomaly="${d.anomaly_count}" />`
          : "";
      const anomalyRect =
        d.anomaly_count > 0
          ? `<rect class="ls-chart-bar" x="${x}" y="${Math.max(anomalyY, marginTop)}" width="${barW}" height="${Math.max(anomalyH, 0)}" rx="4" style="fill:var(--danger-text)"
               data-date="${d.date}" data-normal="${d.normal_count}" data-anomaly="${d.anomaly_count}" />`
          : "";
      return normalRect + anomalyRect + label;
    })
    .join("");

  container.innerHTML = `
    <div class="ls-chart-legend">
      <span class="ls-chart-legend-item"><span class="ls-chart-legend-swatch" style="background:var(--danger-text)"></span>Flagged as Anomaly</span>
      <span class="ls-chart-legend-item"><span class="ls-chart-legend-swatch" style="background:var(--normal-text)"></span>Flagged as Normal</span>
    </div>
    <svg class="ls-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      ${gridLines}
      ${bars}
    </svg>`;

  container.querySelectorAll(".ls-chart-bar").forEach((rect) => {
    rect.addEventListener("pointermove", (evt) => {
      _showTooltip(
        evt,
        `<b>${rect.dataset.date}</b><br>Anomaly: ${rect.dataset.anomaly} · Normal: ${rect.dataset.normal}`
      );
    });
    rect.addEventListener("pointerleave", _hideTooltip);
  });
}

/**
 * Horizontal magnitude bar chart, single hue.
 * items = [{label, sublabel, value}] value in 0-1, sorted desc already.
 */
function renderMagnitudeBarChart(container, items) {
  if (items.length === 0) {
    container.innerHTML = `<div class="ls-empty">Not enough data yet.</div>`;
    return;
  }
  const rowH = 34;
  const marginLeft = 46, marginRight = 56, marginTop = 8;
  const W = 640;
  const H = marginTop + items.length * rowH + 8;
  const plotW = W - marginLeft - marginRight;
  const maxVal = _niceMax(Math.max(...items.map((d) => d.value)));

  const bars = items
    .map((d, i) => {
      const y = marginTop + i * rowH;
      const barH = 18;
      const w = Math.max((d.value / maxVal) * plotW, 2);
      return `
        <text class="ls-chart-axis-text" x="${marginLeft - 8}" y="${y + barH / 2 + 3}" text-anchor="end" font-weight="600">${escapeHtml(d.label)}</text>
        <rect class="ls-chart-bar" x="${marginLeft}" y="${y}" width="${w}" height="${barH}" rx="4" style="fill:var(--primary)"
              data-label="${escapeHtml(d.label)}" data-sublabel="${escapeHtml(d.sublabel || "")}" data-value="${(d.value * 100).toFixed(1)}" />
        <text class="ls-chart-axis-text" x="${marginLeft + w + 6}" y="${y + barH / 2 + 3}">${(d.value * 100).toFixed(0)}%</text>`;
    })
    .join("");

  container.innerHTML = `<svg class="ls-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${bars}</svg>`;

  container.querySelectorAll(".ls-chart-bar").forEach((rect) => {
    rect.addEventListener("pointermove", (evt) => {
      _showTooltip(evt, `<b>${rect.dataset.value}%</b> of anomaly blocks<br>${rect.dataset.sublabel}`);
    });
    rect.addEventListener("pointerleave", _hideTooltip);
  });
}
