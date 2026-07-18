// Determine backend API URL (supports query param ?api_url=... or falls back to localhost in dev / origin in prod)
const urlParams = new URLSearchParams(window.location.search);
const API_URL = urlParams.get('api_url') || (
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000'
        : window.location.origin
);
const MY_PHONE = '919822000001';

const chatArea = document.getElementById('chatArea');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');

let lastMessageCount = 0;

function formatTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function appendMessage(text, type, buttons) {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${type}`;

    // Add text
    const textSpan = document.createElement('span');
    textSpan.textContent = text;
    bubble.appendChild(textSpan);

    // Add time
    const timeSpan = document.createElement('span');
    timeSpan.className = 'message-time';
    timeSpan.textContent = formatTime();
    bubble.appendChild(timeSpan);

    chatArea.appendChild(bubble);

    // WhatsApp-style quick-reply buttons — tapping sends the title back
    if (buttons && buttons.length) {
        const row = document.createElement('div');
        row.className = 'quick-replies';
        buttons.forEach((title) => {
            const btn = document.createElement('button');
            btn.className = 'quick-reply-btn';
            btn.textContent = title;
            btn.addEventListener('click', () => {
                row.remove();
                sendText(title);
            });
            row.appendChild(btn);
        });
        chatArea.appendChild(row);
    }
    scrollToBottom();
}

function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;
    messageInput.value = '';
    await sendText(text);
}

async function sendText(text) {
    // Optimistically show user's message
    appendMessage(text, 'sent');

    // Send to API
    const payload = {
        type: "message",
        payload: {
            id: `msg-${Date.now()}`,
            type: "text",
            source: MY_PHONE,
            sender: {
                phone: MY_PHONE,
                name: "Fisherman Simulator"
            },
            payload: {
                text: text
            }
        }
    };
    
    try {
        await fetch(`${API_URL}/webhook/gupshup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        // Polling will catch the reply shortly
    } catch (err) {
        console.error("Failed to send message:", err);
    }
}

async function pollMessages() {
    try {
        const response = await fetch(`${API_URL}/webhook/gupshup/simulator/messages`);
        if (!response.ok) return;
        
        const messages = await response.json();
        
        if (messages.length > lastMessageCount) {
            // We have new messages from the bot
            for (let i = lastMessageCount; i < messages.length; i++) {
                const msg = messages[i];
                // Only show messages sent back to our phone
                if (msg.phone === MY_PHONE) {
                    appendMessage(msg.text, 'received', msg.buttons);
                }
            }
            lastMessageCount = messages.length;
        }
    } catch (err) {
        // Backend might be restarting or down, ignore gracefully
    }
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Start Polling
setInterval(pollMessages, 1500);

// Initial greeting
appendMessage("Welcome to the Fisherman OS Simulator! Try sending 'Hi' to start the onboarding.", 'received');
