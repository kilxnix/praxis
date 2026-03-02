/**
 * Vib — Frontend Application
 * Vanilla JS WebSocket chat client for The Soul interviewer + Soul Mirror.
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let ws = null;
let userName = "";
let currentMode = "interview";

const welcomeScreen = $("#welcome-screen");
const chatScreen = $("#chat-screen");
const nameForm = $("#name-form");
const nameInput = $("#name-input");
const messageForm = $("#message-form");
const messageInput = $("#message-input");
const messagesContainer = $("#messages");
const modeIndicator = $("#mode-indicator");
const btnStatus = $("#btn-status");
const btnMirror = $("#btn-mirror");
const statusOverlay = $("#status-overlay");
const statusBody = $("#status-body");
const btnCloseStatus = $("#btn-close-status");

function connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
        ws.send(JSON.stringify({ type: "start", name: userName }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        addSystemMessage("Connection lost. Refresh to reconnect.");
    };
}

function handleMessage(msg) {
    removeTypingIndicator();

    switch (msg.type) {
        case "opening":
            addSoulMessage(msg.text);
            break;

        case "response":
            if (msg.mode === "mirror") {
                addMirrorMessage(msg.text);
            } else {
                addSoulMessage(msg.text);
            }
            break;

        case "mode_change":
            currentMode = msg.mode;
            updateModeUI();
            if (msg.text) {
                if (msg.mode === "mirror") {
                    addMirrorMessage(msg.text);
                } else {
                    addSoulMessage(msg.text);
                }
            }
            break;

        case "status":
            showStatus(msg.data);
            break;
    }
}

function addSoulMessage(text) {
    const div = document.createElement("div");
    div.className = "message soul";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function addMirrorMessage(text) {
    const div = document.createElement("div");
    div.className = "message mirror";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function addUserMessage(text) {
    const div = document.createElement("div");
    div.className = "message user";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function addSystemMessage(text) {
    const div = document.createElement("div");
    div.className = "message system";
    div.textContent = text;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function showTypingIndicator() {
    if ($("#typing")) return;
    const div = document.createElement("div");
    div.id = "typing";
    div.className = "typing-indicator";
    div.innerHTML = "<span>.</span><span>.</span><span>.</span>";
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = $("#typing");
    if (el) el.remove();
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function updateModeUI() {
    if (currentMode === "mirror") {
        modeIndicator.textContent = "your soul";
        modeIndicator.classList.add("mirror");
        btnMirror.textContent = "back to interview";
        messageInput.placeholder = "talk to your soul...";
    } else {
        modeIndicator.textContent = "the soul";
        modeIndicator.classList.remove("mirror");
        btnMirror.textContent = "meet your soul";
        messageInput.placeholder = "say something...";
    }
}

function showStatus(data) {
    let html = "";

    const dims = data.dimensions || {};
    const labels = {
        attachment_style: "attachment",
        conflict_style: "conflict style",
        communication_style: "communication",
        vulnerability_comfort: "vulnerability",
        independence_interdependence: "independence",
        openness: "openness",
        conscientiousness: "conscientiousness",
        extroversion: "extroversion",
        agreeableness: "agreeableness",
        neuroticism: "neuroticism",
    };

    for (const [key, label] of Object.entries(labels)) {
        const val = dims[key] || 0;
        const pct = Math.round(val * 100);
        html += `
            <div class="dimension-row">
                <span class="dimension-label">${label}</span>
                <div class="dimension-bar-bg">
                    <div class="dimension-bar" style="width: ${pct}%"></div>
                </div>
                <span class="dimension-value">${pct}%</span>
            </div>
        `;
    }

    html += `
        <div class="status-meta">
            phase: ${data.phase || "—"}<br>
            trust: ${Math.round((data.trust_level || 0) * 100)}%<br>
            matchable: ${data.matchable ? "yes" : "not yet"}<br>
            ${data.open_contradictions > 0 ? `contradictions: ${data.open_contradictions} unresolved` : ""}
        </div>
    `;

    statusBody.innerHTML = html;
    statusOverlay.classList.remove("hidden");
}

nameForm.addEventListener("submit", (e) => {
    e.preventDefault();
    userName = nameInput.value.trim() || "friend";
    welcomeScreen.classList.remove("active");
    chatScreen.classList.add("active");
    connect();
    messageInput.focus();
});

messageForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    addUserMessage(text);
    ws.send(JSON.stringify({ type: "message", text }));
    messageInput.value = "";
    showTypingIndicator();
});

btnStatus.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "command", command: "status" }));
    }
});

btnMirror.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const command = currentMode === "mirror" ? "interview" : "mirror";
    ws.send(JSON.stringify({ type: "command", command }));
    if (command === "mirror") {
        addSystemMessage("switching to soul mirror...");
        showTypingIndicator();
    } else {
        addSystemMessage("returning to interview...");
    }
});

btnCloseStatus.addEventListener("click", () => {
    statusOverlay.classList.add("hidden");
});

statusOverlay.addEventListener("click", (e) => {
    if (e.target === statusOverlay) {
        statusOverlay.classList.add("hidden");
    }
});
