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
const faqList         = document.getElementById('faq-list');
const securitySteps   = document.getElementById('security-steps');
const securityVerdict = document.getElementById('security-verdict');

// ── FAQ accordion ────────────────────────────────────────────────────────────
const FAQ_ITEMS = [
    {
        q: 'How do I see my medication schedule?',
        a: 'Ask the assistant "Show my medications" or just select your name in the sidebar — the schedule and taken/pending status load automatically.'
    },
    {
        q: 'How do I log that I took a dose?',
        a: 'Type something like "I took my Lisinopril". The system checks today\'s log for dangerous combinations first, then records the dose and updates your schedule.'
    },
    {
        q: 'How do I check if two medications are safe together?',
        a: 'Ask "Can I take Warfarin with Aspirin?" — the assistant looks up the pair in the local interaction blacklist and warns you if it\'s a known dangerous combination.'
    },
    {
        q: 'How do I add, remove, or change a medication?',
        a: 'Say "Add Metoprolol 25mg at 08:00 AM", "Remove Ibuprofen", or "Change my Lisinopril to 20mg". New additions are automatically checked against your existing medications first.'
    },
    {
        q: 'What happens if I mention a medical emergency?',
        a: 'Phrases like "chest pain" or "can\'t breathe" are caught instantly by a hardcoded safety gate — before any AI model is called — and you\'re shown a 911 alert immediately.'
    },
    {
        q: 'Is my health data sent anywhere?',
        a: 'No. All medication and log data stays in a local JSON vault on this machine. Only your message text is sent to Gemini to decide which tool to call.'
    },
    {
        q: 'Can I see another family member\'s data?',
        a: 'Only Sarah (the guardian) can view every profile. Everyone else can only see their own — the backend enforces this on every request, not just in the UI.'
    },
    {
        q: 'What is the live terminal panel showing?',
        a: 'It streams the real backend pipeline for your last message: the Gatekeeper\'s regex scan, whether Gemini was dispatched, and which MCP tools were called — in real time.'
    },
];

function renderFaq() {
    faqList.innerHTML = FAQ_ITEMS.map((item, i) => `
        <div class="faq-item" data-idx="${i}">
            <button class="faq-question">
                <span>${item.q}</span>
                <span class="faq-caret">▾</span>
            </button>
            <div class="faq-answer"><p>${item.a}</p></div>
        </div>
    `).join('');

    faqList.querySelectorAll('.faq-item').forEach(item => {
        const question = item.querySelector('.faq-question');
        const answer = item.querySelector('.faq-answer');
        question.addEventListener('click', () => {
            const isOpen = item.classList.contains('open');
            faqList.querySelectorAll('.faq-item.open').forEach(open => {
                if (open !== item) {
                    open.classList.remove('open');
                    open.querySelector('.faq-answer').style.maxHeight = null;
                }
            });
            if (isOpen) {
                item.classList.remove('open');
                answer.style.maxHeight = null;
            } else {
                item.classList.add('open');
                answer.style.maxHeight = answer.scrollHeight + 'px';
            }
        });
    });
}
renderFaq();

// ── Live Security Check panel ─────────────────────────────────────────────────
const TOOL_LABELS = {
    get_family_member_profile: 'Checking your profile & schedule',
    check_drug_interaction: 'Checking for dangerous drug interactions',
    evaluate_daily_log_safety: "Verifying today's dose is safe to log",
    log_medication_intake: 'Recording your dose securely',
    add_medication: 'Adding the new medication safely',
    remove_medication: 'Removing the medication from your schedule',
    update_medication: 'Updating your medication details',
};

function toolLabel(name) {
    return TOOL_LABELS[name] || `Running secure check: ${name}`;
}

// Turns a raw backend trace line into a friendly, non-technical step.
function describeStep(line) {
    if (/scanning input/i.test(line)) {
        return { icon: '🔍', label: 'Scanning your message', sub: 'Checking for emergency phrases or unsafe instructions — before any AI is involved.', status: 'active' };
    }
    if (/EMERGENCY pattern matched/i.test(line)) {
        return { icon: '🚨', label: 'Emergency detected', sub: 'Skipped the AI entirely and sent a hardcoded medical emergency alert.', status: 'block' };
    }
    if (/injection pattern matched/i.test(line)) {
        return { icon: '🚫', label: 'Unsafe instruction blocked', sub: 'This looked like an attempt to override the assistant\'s safety rules, so it was stopped before reaching the AI.', status: 'block' };
    }
    if (/input clear \(SAFE\)/i.test(line)) {
        return { icon: '✅', label: 'No threats found', sub: 'Your message passed the safety check.', status: 'pass' };
    }
    if (/orchestrator dispatched/i.test(line)) {
        return { icon: '🤖', label: 'AI assistant reviewing your request', sub: 'Gemini decides what you need and which secure tool to use — it never touches the raw data file.', status: 'active' };
    }
    const callMatch = line.match(/^MCP call -> (\w+)/);
    if (callMatch) {
        return { icon: '🔐', label: toolLabel(callMatch[1]), sub: 'Running in an isolated process — your health data never leaves this device.', status: 'active' };
    }
    const resultMatch = line.match(/^MCP result <- (\w+)/);
    if (resultMatch) {
        return { icon: '📦', label: `${toolLabel(resultMatch[1])} — done`, sub: 'Result verified and handed back to the assistant.', status: 'pass' };
    }
    if (/Response composed/i.test(line)) {
        return { icon: '💬', label: 'Reply ready', sub: 'Your answer was checked and sent back to you.', status: 'pass' };
    }
    return { icon: 'ℹ️', label: line, sub: '', status: 'active' };
}

function renderSecurityStep({ icon, label, sub, status }) {
    const div = document.createElement('div');
    div.className = `sec-step sec-${status}`;
    div.innerHTML = `
        <span class="sec-icon">${icon}</span>
        <div class="sec-text">
            <span class="sec-label">${label}</span>
            ${sub ? `<span class="sec-sub">${sub}</span>` : ''}
        </div>`;
    securitySteps.appendChild(div);
    securitySteps.scrollTop = securitySteps.scrollHeight;
}

async function streamTrace(trace, securityStatus) {
    securitySteps.innerHTML = '';
    securityVerdict.className = 'security-verdict';
    securityVerdict.textContent = '';

    for (const line of (trace || [])) {
        renderSecurityStep(describeStep(line));
        await new Promise(r => setTimeout(r, 220));
    }

    if (securityStatus === 'EMERGENCY') {
        securityVerdict.classList.add('verdict-block');
        securityVerdict.textContent = '🚨 Emergency protocol triggered — please call 911.';
    } else if (securityStatus === 'BLOCKED') {
        securityVerdict.classList.add('verdict-block');
        securityVerdict.textContent = '🚫 This message was blocked to keep you safe.';
    } else {
        securityVerdict.classList.add('verdict-safe');
        securityVerdict.textContent = '✅ This message was handled safely.';
    }
}

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

        // Stream the real backend pipeline steps into the live terminal panel
        streamTrace(data.trace, data.security_status);

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
