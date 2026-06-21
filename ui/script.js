const API_BASE = 'http://localhost:5001/api';

let currentMemberId = 'member_01';

// DOM refs
const chatMessages    = document.getElementById('chat-messages');
const chatInput       = document.getElementById('chat-input');
const sendBtn         = document.getElementById('send-btn');
const scheduleList    = document.getElementById('schedule-list');
const medListSidebar  = document.getElementById('med-list');
const currentUserName = document.getElementById('current-user-name');
const toast           = document.getElementById('toast');
const onlineDot       = document.getElementById('online-dot');
const statusText      = document.getElementById('status-text');

// ── Toast ──────────────────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg) {
    if (_toastTimer) clearTimeout(_toastTimer);
    toast.textContent = msg;
    toast.classList.add('visible');
    _toastTimer = setTimeout(() => toast.classList.remove('visible'), 2000);
}

// ── Security status indicator ──────────────────────────────────────────────
let _secTimer = null;
function triggerSecurityEvent(status) {
    if (status === 'SAFE') return;
    if (_secTimer) clearTimeout(_secTimer);

    onlineDot.classList.add('danger');
    document.getElementById('status-bar').classList.add('danger');
    statusText.textContent = status === 'EMERGENCY'
        ? 'Emergency Detected — Call 911'
        : 'Security Event Detected';

    _secTimer = setTimeout(() => {
        onlineDot.classList.remove('danger');
        document.getElementById('status-bar').classList.remove('danger');
        statusText.textContent = 'System Online & Secure';
    }, 3000);
}

// ── Typing indicator ───────────────────────────────────────────────────────
function addTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'message assistant typing';
    div.id = 'typing-indicator';
    div.innerHTML = '<span></span><span></span><span></span>';
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

// ── Append chat message ────────────────────────────────────────────────────
function appendMessage(sender, content) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;

    if (typeof content === 'object') {
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(content, null, 2);
        div.appendChild(pre);
    } else {
        // Detect interaction warning (⚠️ prefix) and apply amber styling
        if (sender === 'assistant' && (content.startsWith('⚠️') || content.includes('WARNING') || content.includes('interaction'))) {
            div.classList.add('warning-message');
        }
        div.textContent = content;
    }

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Load member profile ────────────────────────────────────────────────────
async function loadProfile(memberId) {
    try {
        const res = await fetch(`${API_BASE}/profile/${memberId}`);
        const data = await res.json();

        currentUserName.textContent = data.name.split(' ')[0];

        medListSidebar.innerHTML = data.current_medications
            .map(m => `<li>${m}</li>`)
            .join('');

        scheduleList.innerHTML = data.schedule.map(s => `
            <div class="medication-item">
                <div class="med-info">
                    <h4>${s.medication}</h4>
                    <p>${s.dosage} at ${s.time}</p>
                </div>
                <span class="status-badge ${s.taken_today ? 'taken' : 'pending'}">
                    ${s.taken_today ? 'Taken' : 'Pending'}
                </span>
            </div>
        `).join('');

    } catch (err) {
        console.error('Failed to load profile', err);
    }
}

// ── Load dose history ──────────────────────────────────────────────────────
async function loadLogs(memberId) {
    try {
        const res = await fetch(`${API_BASE}/logs/${memberId}`);
        const data = await res.json();
        const logs = data.logs || [];

        if (logs.length === 0) {
            document.getElementById('log-list').innerHTML =
                '<li class="log-empty">No doses logged yet today.</li>';
            return;
        }

        document.getElementById('log-list').innerHTML = logs
            .slice().reverse()
            .map(l => {
                const time = new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                return `<li>
                    <span class="log-med">${l.medication}</span>
                    <span class="log-time">${time}</span>
                </li>`;
            }).join('');

    } catch (err) {
        console.error('Failed to load logs', err);
    }
}

// ── Send chat message ──────────────────────────────────────────────────────
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    chatInput.value = '';
    sendBtn.disabled = true;

    const typingEl = addTypingIndicator();

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, sender_id: currentMemberId })
        });
        const data = await res.json();

        removeTypingIndicator();
        appendMessage('assistant', data.response);

        // Update security indicator for BLOCKED or EMERGENCY events
        if (data.security_status) {
            triggerSecurityEvent(data.security_status);
        }

        // Refresh profile and logs after any action that could change state
        const lower = text.toLowerCase();
        if (lower.includes('took') || lower.includes('log') || lower.includes('taken') || lower.includes('show')) {
            await loadProfile(currentMemberId);
            await loadLogs(currentMemberId);
        }

    } catch (err) {
        removeTypingIndicator();
        appendMessage('assistant', 'Error: Could not connect to the SafeHealth server.');
    } finally {
        sendBtn.disabled = false;
    }
}

// ── Member card switching ──────────────────────────────────────────────────
document.querySelectorAll('.member-card').forEach(card => {
    card.addEventListener('click', async () => {
        if (card.classList.contains('active')) return;

        const name = card.querySelector('.name').textContent;
        showToast(`Switching to ${name}'s secure session…`);

        document.querySelector('.member-card.active').classList.remove('active');
        card.classList.add('active');
        currentMemberId = card.dataset.id;

        await loadProfile(currentMemberId);
        await loadLogs(currentMemberId);
    });
});

// ── Event listeners ────────────────────────────────────────────────────────
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') sendMessage();
});

// ── Initial load ───────────────────────────────────────────────────────────
loadProfile(currentMemberId);
loadLogs(currentMemberId);
