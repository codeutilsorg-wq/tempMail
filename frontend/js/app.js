/**
 * EasyTempInbox - Frontend Application
 * Handles inbox creation, email polling, and UI interactions
 */

// Configuration
//const API_BASE_URL = 'https://your-api-gateway-url.amazonaws.com'; // Replace with actual API Gateway URL
//const API_BASE_URL = 'http://localhost:8001';  // Local testing
const API_BASE_URL = 'https://eagu6a93n6.execute-api.us-east-1.amazonaws.com';  // Production
const POLLING_INTERVAL_START = 5000; // Start at 5 seconds
const POLLING_INTERVAL_MAX = 30000; // Max 30 seconds
const POLLING_BACKOFF_MULTIPLIER = 1.5;

// State
let currentInbox = null;
let pollingInterval = null;
let pollingIntervalMs = POLLING_INTERVAL_START;
let countdownInterval = null;

// DOM Elements
const generateBtn = document.getElementById('generate-btn');
const copyBtn = document.getElementById('copy-btn');
const refreshBtn = document.getElementById('refresh-btn');
const backBtn = document.getElementById('back-btn');
const newEmailBtn = document.getElementById('new-email-btn');
const emailDisplay = document.getElementById('email-display');
const emailAddress = document.getElementById('email-address');
const emailCount = document.getElementById('email-count');
const countdown = document.getElementById('countdown');
const loading = document.getElementById('loading');
const inboxSection = document.getElementById('inbox-section');
const emailList = document.getElementById('email-list');
const emailDetailSection = document.getElementById('email-detail-section');
const emailDetail = document.getElementById('email-detail');
const ttlSelect = document.getElementById('ttl-select');

// Event Listeners
generateBtn.addEventListener('click', createInbox);
copyBtn.addEventListener('click', copyEmailAddress);
refreshBtn.addEventListener('click', refreshInbox);
backBtn.addEventListener('click', showInboxView);
newEmailBtn.addEventListener('click', generateNewEmail);

// Generate new email function
function generateNewEmail() {
    resetUI();
    createInbox();
}

// API Functions
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function createInbox() {
    const ttl = parseInt(ttlSelect.value);

    // Show loading
    generateBtn.style.display = 'none';
    loading.style.display = 'block';

    try {
        const data = await apiRequest('/api/inbox', {
            method: 'POST',
            body: JSON.stringify({ ttl })
        });

        currentInbox = data;

        // Update UI
        emailAddress.value = data.address;
        emailDisplay.style.display = 'block';
        loading.style.display = 'none';
        inboxSection.style.display = 'block';

        // Start countdown
        startCountdown(data.expires_at);

        // Start polling
        startPolling();

        // Initial fetch
        await fetchEmails();

    } catch (error) {
        alert('Failed to create inbox: ' + error.message);
        generateBtn.style.display = 'block';
        loading.style.display = 'none';
    }
}

async function fetchEmails() {
    if (!currentInbox) return;

    try {
        const data = await apiRequest(`/api/inbox/${currentInbox.id}/emails`);

        // Update email count
        emailCount.textContent = data.count;

        // Render email list
        renderEmailList(data.emails);

    } catch (error) {
        console.error('Failed to fetch emails:', error);
    }
}

async function fetchEmailDetail(inboxId, emailId) {
    try {
        const data = await apiRequest(`/api/email/${inboxId}/${emailId}`);
        currentEmailId = emailId; // Store for attachment downloads
        renderEmailDetail(data);
    } catch (error) {
        alert('Failed to fetch email: ' + error.message);
    }
}

// Store current email ID for attachment downloads
let currentEmailId = null;

async function downloadAttachment(attachmentId) {
    if (!currentInbox || !currentEmailId) {
        alert('Unable to download attachment');
        return;
    }

    try {
        const data = await apiRequest(`/api/attachment/${currentInbox.id}/${currentEmailId}/${attachmentId}`);

        // Open the pre-signed URL in a new tab to trigger download
        window.open(data.download_url, '_blank');
    } catch (error) {
        alert('Failed to download attachment: ' + error.message);
    }
}

async function getInboxStatus() {
    if (!currentInbox) return;

    try {
        const data = await apiRequest(`/api/inbox/${currentInbox.id}/status`);

        if (!data.exists) {
            // Inbox expired
            stopPolling();
            stopCountdown();
            alert('Your inbox has expired');
            resetUI();
            return;
        }

        // Update email count
        emailCount.textContent = data.email_count;

        // If count changed, fetch emails
        const currentCount = parseInt(emailCount.textContent);
        if (data.email_count !== currentCount) {
            await fetchEmails();
        }

    } catch (error) {
        console.error('Failed to get inbox status:', error);
    }
}

// UI Functions
function renderEmailList(emails) {
    if (emails.length === 0) {
        emailList.innerHTML = `
            <div class="empty-state">
                <p>📭 No emails yet</p>
                <p class="hint">Emails sent to your temporary address will appear here</p>
            </div>
        `;
        return;
    }

    emailList.innerHTML = emails.map(email => `
        <div class="email-item" onclick="viewEmail('${email.email_id}')">
            <div class="email-item-header">
                <span class="email-from">${escapeHtml(email.from_address)}</span>
                <span class="email-time">${formatTime(email.received_at)}</span>
            </div>
            <div class="email-subject">${escapeHtml(email.subject)}</div>
        </div>
    `).join('');
}

function renderEmailDetail(email) {
    // For HTML emails, we need to escape quotes for srcdoc attribute but preserve HTML
    const escapedHtmlForSrcdoc = email.html_body ?
        email.html_body.replace(/"/g, '&quot;') : '';

    // Format file size
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // Build attachments HTML
    let attachmentsHtml = '';
    if (email.attachments && email.attachments.length > 0) {
        attachmentsHtml = `
            <div class="email-attachments">
                <div class="attachments-header">
                    <span>📎</span> Attachments (${email.attachments.length})
                </div>
                <div class="attachments-list">
                    ${email.attachments.map(att => `
                        <div class="attachment-item" data-attachment-id="${att.id}">
                            <span class="attachment-name">${escapeHtml(att.filename)}</span>
                            <span class="attachment-size">${formatFileSize(att.size)}</span>
                            <button class="btn-download" onclick="downloadAttachment('${att.id}')">
                                Download
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    emailDetail.innerHTML = `
        <div class="email-detail-header">
            <h3>${escapeHtml(email.subject)}</h3>
        </div>
        <div class="email-detail-meta">
            <div class="meta-row">
                <span class="meta-label">From:</span>
                <span>${escapeHtml(email.from_address)}</span>
            </div>
            <div class="meta-row">
                <span class="meta-label">Received:</span>
                <span>${formatDateTime(email.received_at)}</span>
            </div>
        </div>
        ${attachmentsHtml}
        <div class="email-body">
            ${email.html_body ?
            `<iframe srcdoc="${escapedHtmlForSrcdoc}"></iframe>` :
            `<pre>${escapeHtml(email.text_body)}</pre>`
        }
        </div>
    `;

    // Show email detail view
    inboxSection.style.display = 'none';
    emailDetailSection.style.display = 'block';
}

function showInboxView() {
    emailDetailSection.style.display = 'none';
    inboxSection.style.display = 'block';
}

// Polling
function startPolling() {
    stopPolling(); // Clear any existing interval

    pollingInterval = setInterval(() => {
        getInboxStatus();

        // Exponential backoff
        pollingIntervalMs = Math.min(
            pollingIntervalMs * POLLING_BACKOFF_MULTIPLIER,
            POLLING_INTERVAL_MAX
        );

        // Restart with new interval
        startPolling();

    }, pollingIntervalMs);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// Countdown Timer
function startCountdown(expiresAt) {
    stopCountdown();

    function updateCountdown() {
        const now = Math.floor(Date.now() / 1000);
        const remaining = expiresAt - now;

        if (remaining <= 0) {
            countdown.textContent = 'EXPIRED';
            stopCountdown();
            stopPolling();
            return;
        }

        const hours = Math.floor(remaining / 3600);
        const minutes = Math.floor((remaining % 3600) / 60);
        const seconds = remaining % 60;

        countdown.textContent = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
    }

    updateCountdown();
    countdownInterval = setInterval(updateCountdown, 1000);
}

function stopCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
}

// Helper Functions
function copyEmailAddress() {
    emailAddress.select();
    document.execCommand('copy');

    // Visual feedback
    const originalText = copyBtn.textContent;
    copyBtn.textContent = '✓ Copied!';
    setTimeout(() => {
        copyBtn.textContent = originalText;
    }, 2000);
}

function refreshInbox() {
    pollingIntervalMs = POLLING_INTERVAL_START; // Reset backoff
    fetchEmails();
}

function viewEmail(emailId) {
    fetchEmailDetail(currentInbox.id, emailId);
}

function resetUI() {
    currentInbox = null;
    emailDisplay.style.display = 'none';
    inboxSection.style.display = 'none';
    emailDetailSection.style.display = 'none';
    generateBtn.style.display = 'block';
    emailAddress.value = '';
    emailCount.textContent = '0';
    countdown.textContent = '--:--:--';
    pollingIntervalMs = POLLING_INTERVAL_START;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(timestamp) {
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

    return date.toLocaleDateString();
}

function formatDateTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

function pad(num) {
    return num.toString().padStart(2, '0');
}

// Initialize
console.log('EasyTempInbox initialized');
