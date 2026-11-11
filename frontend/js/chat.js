let chatHistory = [];

function appendMessage(role, content) {
  const el = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = `ls-chat-row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "ls-chat-bubble";
  bubble.textContent = content;
  row.appendChild(bubble);
  el.appendChild(row);
  el.scrollTop = el.scrollHeight;
  return bubble;
}

const CHAT_SUGGESTIONS = [
  "Why was blk_7333006829265792396 flagged?",
  "How much does evidence improve accuracy?",
  "What should I review first today?",
];

function showSuggestions() {
  const el = document.getElementById("chat-suggestions");
  el.hidden = false;
  el.innerHTML = CHAT_SUGGESTIONS.map(
    (s) => `<button type="button" class="ls-chat-suggestion">${escapeHtml(s)}</button>`
  ).join("");
  el.querySelectorAll(".ls-chat-suggestion").forEach((btn, i) => {
    btn.addEventListener("click", () => {
      document.getElementById("chat-input").value = CHAT_SUGGESTIONS[i];
      sendMessage();
    });
  });
}

function hideSuggestions() {
  document.getElementById("chat-suggestions").hidden = true;
}

function showGreeting() {
  document.getElementById("chat-messages").innerHTML = "";
  appendMessage(
    "assistant",
    "Hi, I can answer questions about analyzed blocks, the priority queue and evaluation results. Try one of the suggestions below."
  );
  showSuggestions();
}

async function sendMessage() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const message = input.value.trim();
  if (!message) return;

  hideSuggestions();
  appendMessage("user", message);
  input.value = "";
  sendBtn.disabled = true;
  const thinkingBubble = appendMessage("assistant", "…thinking…");

  try {
    const res = await api.chat(message, chatHistory);
    thinkingBubble.innerHTML = formatLLMText(res.reply);
    chatHistory.push({ role: "user", content: message });
    chatHistory.push({ role: "assistant", content: res.reply });
  } catch (err) {
    thinkingBubble.parentElement.classList.remove("assistant");
    thinkingBubble.parentElement.classList.add("error");
    thinkingBubble.textContent = `Sorry, I couldn't get a response just now. Please try again in a moment. (${err.message})`;
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

document.getElementById("chat-send-btn").onclick = sendMessage;
document.getElementById("chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});
document.getElementById("chat-clear-btn").onclick = () => {
  chatHistory = [];
  showGreeting();
};
document.getElementById("topbar-search").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const id = e.target.value.trim();
    if (id) window.location.href = `analyze.html?block=${encodeURIComponent(id)}`;
  }
});

showGreeting();
