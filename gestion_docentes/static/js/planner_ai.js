document.addEventListener('DOMContentLoaded', function () {
    const aiElements = {
        widget: document.querySelector('#ai-chat-widget'),
        window: document.querySelector('#ai-chat-window'),
        messages: document.querySelector('#ai-chat-messages'),
        input: document.querySelector('#ai-chat-input'),
        sendBtn: document.querySelector('#send-ai-message'),
        toggleBtn: document.querySelector('#toggle-ai-chat'),
        closeBtn: document.querySelector('#close-chat')
    };

    let chatHistory = [];
    let isTyping = false;

    if (!aiElements.toggleBtn) return;

    // --- UTILS ---
    function addMessage(text, role = 'model') {
        const chatDiv = document.createElement('div');
        chatDiv.className = `chat ${role === 'user' ? 'chat-end' : 'chat-start'}`;

        chatDiv.innerHTML = `
            <div class="chat-bubble ${role === 'user' ? 'bg-primary text-primary-content' : 'chat-bubble-primary'} text-sm">
                ${text.replace(/\n/g, '<br>')}
            </div>
        `;
        aiElements.messages.appendChild(chatDiv);
        aiElements.messages.scrollTop = aiElements.messages.scrollHeight;
    }

    function showTyping() {
        if (isTyping) return;
        isTyping = true;
        const typingDiv = document.createElement('div');
        typingDiv.id = 'ai-typing';
        typingDiv.className = 'chat chat-start';
        typingDiv.innerHTML = `
            <div class="chat-bubble chat-bubble-primary opacity-70 text-xs">
                <span class="loading loading-dots loading-xs"></span> escribiendo...
            </div>
        `;
        aiElements.messages.appendChild(typingDiv);
        aiElements.messages.scrollTop = aiElements.messages.scrollHeight;
    }

    function hideTyping() {
        isTyping = false;
        const typingDiv = document.querySelector('#ai-typing');
        if (typingDiv) typingDiv.remove();
    }

    // --- CORE LOGIC ---
    async function sendMessage() {
        const message = aiElements.input.value.trim();
        if (!message || isTyping) return;

        aiElements.input.value = '';
        addMessage(message, 'user');
        showTyping();

        try {
            const espId = document.querySelector('#especialidad')?.value;
            const semNum = document.querySelector('#semestre_cursado')?.value;

            const response = await fetch('/api/planner-chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.PlannerConfig?.csrfToken
                },
                body: JSON.stringify({
                    message: message,
                    history: chatHistory,
                    especialidad_id: espId,
                    semestre_cursado: semNum
                })
            });

            const data = await response.json();
            hideTyping();

            if (data.status === 'success') {
                addMessage(data.data.reply, 'model');
                chatHistory = data.data.history;

                // Si el mensaje indica un cambio, podríamos recargar el planificador
                if (data.data.reply.toLowerCase().includes('actualizado') ||
                    data.data.reply.toLowerCase().includes('movido') ||
                    data.data.reply.toLowerCase().includes('listo')) {
                    if (window.loadPlannerData) window.loadPlannerData();
                }
            } else {
                addMessage(`Error: ${data.message}`, 'model');
            }
        } catch (error) {
            hideTyping();
            addMessage(`Ocurrió un error al conectar con el asistente: ${error.message}`, 'model');
        }
    }

    // --- EVENTS ---
    aiElements.toggleBtn.addEventListener('click', () => {
        aiElements.window.classList.toggle('show');
        if (aiElements.window.classList.contains('show')) {
            aiElements.input.focus();
        }
    });

    aiElements.closeBtn.addEventListener('click', () => {
        aiElements.window.classList.remove('show');
    });

    aiElements.sendBtn.addEventListener('click', sendMessage);
    aiElements.input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
});
