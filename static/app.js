/* -----------------------------------------------
   Vib -- Agentic Dating Frontend
   ----------------------------------------------- */

(function () {
    'use strict';

    let ws = null;
    let sessionData = null;
    let inMirrorMode = false;
    let userName = null;

    // -- DOM refs --

    const entryScreen = document.getElementById('entry-screen');
    const chatScreen = document.getElementById('chat-screen');
    const mirrorScreen = document.getElementById('mirror-screen');
    const nameInput = document.getElementById('name-input');
    const startBtn = document.getElementById('start-btn');
    const phaseIndicator = document.getElementById('phase-indicator');
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const soulBtn = document.getElementById('soul-btn');
    const soulOverlay = document.getElementById('soul-overlay');
    const closeSoul = document.getElementById('close-soul');
    const soulBody = document.getElementById('soul-body');
    const mirrorSection = document.getElementById('mirror-section');
    const mirrorBtn = document.getElementById('mirror-btn');
    const mirrorMessages = document.getElementById('mirror-messages');
    const mirrorForm = document.getElementById('mirror-form');
    const mirrorInput = document.getElementById('mirror-input');
    const exitMirrorBtn = document.getElementById('exit-mirror-btn');

    // -- Phase labels --

    const PHASE_LABELS = {
        'ARRIVAL': 'getting started',
        'DAILY_RHYTHM': 'learning your rhythm',
        'ATTUNED': 'attuned',
        'COMPANION': 'companion',
    };

    // -- WebSocket --

    function connect() {
        const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(protocol + '://' + location.host + '/ws');

        ws.onopen = function () {
            // Connection ready, wait for user to start
        };

        ws.onmessage = function (event) {
            var msg = JSON.parse(event.data);
            handleMessage(msg);
        };

        ws.onclose = function () {
            setTimeout(connect, 2000);
        };
    }

    function send(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }

    // -- Message handler --

    function handleMessage(msg) {
        switch (msg.type) {
            case 'started':
                sessionData = msg.data;
                updatePhase(msg.data.phase);
                addMessage(msg.greeting, 'vib');
                if (!msg.has_llm) {
                    addSystemMessage('Running without LLM -- responses will be limited');
                }
                break;

            case 'response':
                sessionData = msg.data;
                updatePhase(msg.data.phase);
                addMessage(msg.text, 'vib');
                enableInput();
                break;

            case 'status':
                sessionData = msg.data;
                renderSoulPanel(msg.data);
                break;

            case 'mirror_started':
                sessionData = msg.data;
                enterMirrorUI();
                break;

            case 'mirror_response':
                addMirrorMessage(msg.text, 'soul');
                enableMirrorInput();
                break;

            case 'mirror_exited':
                sessionData = msg.data;
                exitMirrorUI();
                break;

            case 'entry_logged':
                console.log('Entry logged:', msg.payload.entry_id);
                break;

            case 'error':
                addSystemMessage(msg.message);
                enableInput();
                break;
        }
    }

    // -- UI helpers --

    function showScreen(screen) {
        entryScreen.classList.remove('active');
        chatScreen.classList.remove('active');
        mirrorScreen.classList.remove('active');
        screen.classList.add('active');
    }

    function updatePhase(phase) {
        phaseIndicator.textContent = PHASE_LABELS[phase] || phase.toLowerCase();
    }

    function addMessage(text, sender) {
        var div = document.createElement('div');
        div.className = 'msg msg-' + sender;

        var bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.textContent = text;

        div.appendChild(bubble);
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addSystemMessage(text) {
        var div = document.createElement('div');
        div.className = 'msg msg-system';
        div.textContent = text;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addMirrorMessage(text, sender) {
        var div = document.createElement('div');
        div.className = 'msg msg-' + sender;

        var bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.textContent = text;

        div.appendChild(bubble);
        mirrorMessages.appendChild(div);
        mirrorMessages.scrollTop = mirrorMessages.scrollHeight;
    }

    function disableInput() {
        chatInput.disabled = true;
        chatForm.querySelector('.btn-send').disabled = true;
    }

    function enableInput() {
        chatInput.disabled = false;
        chatForm.querySelector('.btn-send').disabled = false;
        chatInput.focus();
    }

    function disableMirrorInput() {
        mirrorInput.disabled = true;
        mirrorForm.querySelector('.btn-send').disabled = true;
    }

    function enableMirrorInput() {
        mirrorInput.disabled = false;
        mirrorForm.querySelector('.btn-send').disabled = false;
        mirrorInput.focus();
    }

    // -- Soul panel --

    function renderSoulPanel(data) {
        var r = data.readiness;
        var html = '';

        // Overall readiness
        html += '<div class="soul-readiness">';
        html += '<div class="readiness-label">soul readiness</div>';
        html += '<div class="readiness-bar-track">';
        html += '<div class="readiness-bar-fill" style="width:' + (r.overall_confidence * 100) + '%"></div>';
        html += '</div>';
        html += '<div class="readiness-pct">' + (r.overall_confidence * 100).toFixed(0) + '%</div>';
        html += '</div>';

        // Session info
        html += '<div class="soul-meta">';
        html += 'Phase: ' + (PHASE_LABELS[r.phase] || r.phase) + '<br>';
        html += 'Attunement: ' + (r.attunement_level * 100).toFixed(0) + '%<br>';
        html += 'Sessions: ' + r.sessions_completed;
        if (r.open_contradictions > 0) {
            html += '<br>Contradictions: ' + r.open_contradictions;
        }
        html += '</div>';

        // Dimensions
        html += '<div class="soul-dimensions">';
        var dims = r.dimensions;
        for (var dim in dims) {
            var pct = (dims[dim] * 100).toFixed(0);
            var label = dim.replace(/_/g, ' ');
            html += '<div class="dim-row">';
            html += '<span class="dim-name">' + label + '</span>';
            html += '<div class="dim-track"><div class="dim-fill" style="width:' + pct + '%"></div></div>';
            html += '<span class="dim-pct">' + pct + '%</span>';
            html += '</div>';
        }
        html += '</div>';

        soulBody.innerHTML = html;

        // Show mirror button if matchable or if overall confidence > 30%
        if (r.matchable || r.overall_confidence > 0.3) {
            mirrorSection.classList.remove('hidden');
        } else {
            mirrorSection.classList.add('hidden');
        }

        soulOverlay.classList.remove('hidden');
    }

    // -- Mirror mode --

    function enterMirrorUI() {
        inMirrorMode = true;
        soulOverlay.classList.add('hidden');
        showScreen(mirrorScreen);
        mirrorMessages.innerHTML = '';
        addMirrorMessage("Hey. I'm your Soul -- a version of you built from everything we've talked about. Ask me anything.", 'soul');
        mirrorInput.focus();
    }

    function exitMirrorUI() {
        inMirrorMode = false;
        showScreen(chatScreen);
        chatInput.focus();
    }

    // -- Event listeners --

    startBtn.addEventListener('click', function () {
        var name = nameInput.value.trim();
        if (!name) {
            nameInput.focus();
            return;
        }
        userName = name;
        send({ type: 'start', name: name });
        showScreen(chatScreen);
    });

    nameInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            startBtn.click();
        }
    });

    chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var text = chatInput.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        send({ type: 'message', text: text });
        chatInput.value = '';
        disableInput();
    });

    soulBtn.addEventListener('click', function () {
        send({ type: 'status' });
    });

    closeSoul.addEventListener('click', function () {
        soulOverlay.classList.add('hidden');
    });

    soulOverlay.addEventListener('click', function (e) {
        if (e.target === soulOverlay) {
            soulOverlay.classList.add('hidden');
        }
    });

    mirrorBtn.addEventListener('click', function () {
        send({ type: 'enter_mirror' });
    });

    mirrorForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var text = mirrorInput.value.trim();
        if (!text) return;

        addMirrorMessage(text, 'user');
        send({ type: 'mirror_message', text: text });
        mirrorInput.value = '';
        disableMirrorInput();
    });

    exitMirrorBtn.addEventListener('click', function () {
        send({ type: 'exit_mirror' });
    });

    // -- Init --
    connect();

})();
