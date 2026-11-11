async function loadHomeStats() {
  try {
    const stats = await api.stats();
    document.getElementById("home-stat-blocks").textContent = stats.total_blocks.toLocaleString();
    document.getElementById("home-stat-anomalies").textContent = stats.anomaly_count.toLocaleString();

    const ev = stats.latest_evaluation;
    if (ev && ev.status === "completed") {
      document.getElementById("home-stat-accuracy").textContent = `${(ev.grounded_accuracy * 100).toFixed(0)}%`;
      const multiplier = ev.grounded_accuracy / ev.ungrounded_accuracy;
      document.getElementById("home-stat-delta").textContent = `${multiplier.toFixed(1)}×`;
    } else {
      document.getElementById("home-stat-accuracy").textContent = "—";
      document.getElementById("home-stat-delta").textContent = "—";
    }

    const chatAnswer = document.getElementById("home-chat-answer");
    if (chatAnswer) {
      chatAnswer.textContent =
        `Start with the top of the priority queue — ${stats.flagged_unreviewed.toLocaleString()} blocks are flagged and still unreviewed.`;
    }
  } catch (err) {
    document.querySelectorAll("#stats-strip .ls-home-stat-value").forEach((el) => {
      el.textContent = "—";
    });
  }
}

loadHomeStats();
