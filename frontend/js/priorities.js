const PAGE_SIZE = 25;
let currentOffset = 0;

async function loadSummary() {
  const el = document.getElementById("summary-card");
  try {
    const stats = await api.stats();
    el.innerHTML = `
      <b>${stats.flagged_unreviewed.toLocaleString()}</b> flagged case(s) still need a look
      <span class="ls-muted">(out of ${stats.flagged_by_model.toLocaleString()} the AI has ever flagged)</span>`;
  } catch (err) {
    el.innerHTML = `<div class="ls-empty">Failed to load summary: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadPriorities(offset = 0) {
  currentOffset = offset;
  const unreviewedOnly = document.getElementById("unreviewed-only").checked;
  const listEl = document.getElementById("priorities-list");
  listEl.innerHTML = `<div class="ls-empty"><span class="ls-spinner"></span> Loading…</div>`;

  const params = {
    predicted_label: "Anomaly",
    sort: "confidence_desc",
    limit: PAGE_SIZE,
    offset,
  };
  if (unreviewedOnly) params.reviewed = false;

  try {
    const blocks = await api.listBlocks(params);
    if (blocks.length === 0) {
      listEl.innerHTML = `<div class="ls-empty">${
        unreviewedOnly ? "Nothing pending — every flagged case has been reviewed." : "No flagged blocks found."
      }</div>`;
    } else {
      listEl.innerHTML = `
        <div class="ls-table-wrap">
          <table class="ls-table">
            <thead><tr><th>#</th><th>Block</th><th>Priority</th><th title="How sure the AI is in this verdict">Confidence</th><th title="Why this is ranked where it is, when confidence alone ties">Why first</th><th>Reviewed?</th><th></th></tr></thead>
            <tbody>
              ${blocks
                .map(
                  (b, i) => `
                <tr>
                  <td class="ls-muted">${offset + i + 1}</td>
                  <td>${escapeHtml(b.block_id)}</td>
                  <td>${severityHtml(b.predicted_confidence)}</td>
                  <td title="How sure the AI is in this verdict">${b.predicted_confidence !== null ? (b.predicted_confidence * 100).toFixed(1) + "%" : "—"}</td>
                  <td class="ls-muted">${b.total_event_count !== null && b.total_event_count !== undefined ? `${b.has_error_event ? "Error event" : "No error event"} · ${b.total_event_count} events` : "—"}</td>
                  <td>${b.reviewed_at ? `<span class="ls-badge ls-badge-muted" title="Reviewed ${formatDate(b.reviewed_at)}">Reviewed</span>` : '<span class="ls-muted">Not yet</span>'}</td>
                  <td><button class="ls-btn ls-btn-ghost review-btn" data-block-id="${escapeHtml(b.block_id)}">Review</button></td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;
      listEl.querySelectorAll(".review-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const blockId = btn.dataset.blockId;
          btn.disabled = true;
          btn.textContent = "Marking reviewed…";
          try {
            // This is the ONLY action that marks a block reviewed — running
            // Analyze or Live Simulation on it never does.
            await api.reviewBlock(blockId);
            window.location.href = `analyze.html?block=${encodeURIComponent(blockId)}`;
          } catch (err) {
            btn.disabled = false;
            btn.textContent = "Review";
            alert(`Couldn't mark this reviewed: ${err.message}`);
          }
        });
      });
    }

    document.getElementById("pagination").innerHTML = `
      <button class="ls-btn ls-btn-ghost" id="prev-page" ${offset === 0 ? "disabled" : ""}>← Previous</button>
      <span class="ls-muted">Showing ${offset + 1}–${offset + blocks.length}</span>
      <button class="ls-btn ls-btn-ghost" id="next-page" ${blocks.length < PAGE_SIZE ? "disabled" : ""}>Next →</button>`;
    document.getElementById("prev-page").onclick = () => loadPriorities(Math.max(0, offset - PAGE_SIZE));
    document.getElementById("next-page").onclick = () => loadPriorities(offset + PAGE_SIZE);
  } catch (err) {
    listEl.innerHTML = `<div class="ls-empty">Failed to load priorities: ${escapeHtml(err.message)}</div>`;
  }
}

document.getElementById("unreviewed-only").addEventListener("change", () => loadPriorities(0));

loadSummary();
loadPriorities(0);
