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

function showGreeting() {
  document.getElementById("chat-messages").innerHTML = "";
  appendMessage(
    "assistant",
    "Hi! Ask me about current stats, recent activity, top priority cases, or a specific block ID — I'll answer using the system's real, current data."
  );
}

async function sendMessage() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const message = input.value.trim();
  if (!message) return;

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
    thinkingBubble.textContent = `Couldn't get a response: ${err.message}`;
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

showGreeting();
