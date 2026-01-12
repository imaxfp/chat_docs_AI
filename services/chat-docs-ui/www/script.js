document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const debugToggle = document.getElementById('debug-mode');

    // API Endpoint (Injected at runtime)
    const API_URL = '__CHAT_API_URL__';

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const message = userInput.value.trim();
        if (!message) return;

        // Add user message to UI
        addMessage(message, 'user');
        userInput.value = '';

        // Show typing indicator
        const typingId = showTypingIndicator();

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: message,
                    limit: 3,
                    debug_flag: debugToggle.checked
                }),
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const data = await response.json();

            // Remove typing indicator
            removeTypingIndicator(typingId);

            // Add assistant response
            addMessage(data.final_llm_answer, 'assistant', data);

        } catch (error) {
            console.error('Error:', error);
            removeTypingIndicator(typingId);
            addMessage(`Sorry, I encountered an error: ${error.message}. Please make sure the backend is running at ${API_URL}`, 'assistant error');
        }
    });

    function addMessage(text, sender, data = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        let contentHtml = `<div class="message-content">${marked.parse(text)}</div>`;

        // Add sources if available and in debug mode
        if (data && data.sources && debugToggle.checked) {
            let sourcesHtml = '<div class="sources"><strong>Sources (Click to expand):</strong>';
            data.sources.forEach((source, index) => {
                const sourceId = `source-${Date.now()}-${index}`;
                sourcesHtml += `
                    <div class="source-item" onclick="toggleSource('${sourceId}')">
                        <div class="source-header">
                            <span>${source.pdf_name} (p. ${source.page_number})</span>
                            <span class="score">Score: ${source.score.toFixed(3)}</span>
                        </div>
                        <div id="${sourceId}" class="source-details" style="display: none;">
                            <div class="source-info-grid">
                                <div class="info-item"><strong>Chunk ID:</strong> <span>${source.chunk_id}</span></div>
                                <div class="info-item"><strong>Chunk Index:</strong> <span>${source.chunk_index}</span></div>
                                <div class="info-item"><strong>PDF ID:</strong> <span>${source.pdf_id}</span></div>
                            </div>
                            <div class="source-text"><strong>Full Text:</strong><br>${source.full_text}</div>
                            <div class="source-meta"><strong>Additional Metadata:</strong><pre>${JSON.stringify(source.metadata, null, 2)}</pre></div>
                        </div>
                    </div>
                `;
            });
            sourcesHtml += '</div>';
            contentHtml += sourcesHtml;
        }

        // Add debug info if available
        if (data && data.debug_info && debugToggle.checked) {
            contentHtml += `
                <div class="debug-info">
                    Refined Query: ${data.debug_info.refined_query || 'N/A'}<br>
                    Duration: ${data.duration_seconds}s
                </div>
            `;
        }

        messageDiv.innerHTML = contentHtml;
        chatContainer.appendChild(messageDiv);

        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant typing';
        typingDiv.id = id;
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        chatContainer.appendChild(typingDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return id;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // Global toggle function
    window.toggleSource = (id) => {
        const el = document.getElementById(id);
        if (el) {
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }
    };
});
