const API_BASE = 'http://localhost:8000';

async function api(path, opts = {}) {
    const res = await fetch(API_BASE + path, opts);
    if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(`${path} → ${res.status}: ${detail}`);
    }
    return res.json();
}

async function apiPost(path, body) {
    return api(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
}

function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Common functions
function initClock() {
    const clockEl = document.getElementById('liveClock');
    if (!clockEl) return;
    setInterval(() => {
        const now = new Date();
        const ist = new Date(now.getTime() + (5.5 * 60 * 60 * 1000));
        clockEl.textContent = ist.toISOString().substring(11, 19) + ' IST';
    }, 1000);
}

function updateConnectionStatus(ok, text) {
    const statusText = document.getElementById('statusText');
    const statusInd = document.getElementById('statusIndicator');
    if (statusText) statusText.textContent = text;
    if (statusInd) statusInd.classList.toggle('offline', !ok);
}

// Check role toggle on load
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    const roleToggle = document.getElementById('roleToggle');
    if (roleToggle) {
        document.body.setAttribute('data-role', roleToggle.value);
        roleToggle.addEventListener('change', (e) => {
            document.body.setAttribute('data-role', e.target.value);
            // Dispatch event so pages can react if needed
            window.dispatchEvent(new CustomEvent('roleChanged', { detail: e.target.value }));
        });
    }
});
