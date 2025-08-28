// TODO: Refactor this into a separate static JS file
document.addEventListener('DOMContentLoaded', function() {
    // --- STATE ---
    const currentUserId = currentUser.id;
    let activeConversationId = null;
    let conversations = new Map();
    let activeConversationMessages = [];
    let selectedParticipants = new Map();
    let chatSocket = null;
    let searchTimeout = null;

    // --- DOM ELEMENTS ---
    const conversationListEl = document.getElementById('conversation-list');
    const messageListEl = document.getElementById('message-list');
    const chatPlaceholderEl = document.getElementById('chat-placeholder');
    const chatHeaderEl = document.getElementById('chat-header');
    const chatHeaderAvatarEl = document.getElementById('chat-header-avatar');
    const chatHeaderNameEl = document.getElementById('chat-header-name');
    const chatHeaderParticipantsEl = document.getElementById('chat-header-participants');
    const chatInputContainerEl = document.getElementById('chat-input-container');
    const chatFormEl = document.getElementById('chat-form');
    const chatMessageInputEl = document.getElementById('chat-message-input');

    // Modal Elements
    const newChatBtn = document.getElementById('new-chat-btn');
    const newChatModal = document.getElementById('new-chat-modal');
    const userSearchInput = document.getElementById('user-search-input');
    const userSearchResultsEl = document.getElementById('user-search-results');
    const selectedParticipantsEl = document.getElementById('selected-participants');
    const isGroupCheckbox = document.getElementById('is-group-chat-checkbox');
    const groupNameContainer = document.getElementById('group-name-container');
    const groupNameInput = document.getElementById('group-name-input');
    const startConversationBtn = document.getElementById('start-conversation-btn');
    const emojiBtn = document.getElementById('emoji-btn');
    const emojiPicker = document.getElementById('emoji-picker');

    // --- UTILS ---
    function getCsrfToken() {
        const chatContainer = document.getElementById('chat-container');
        return chatContainer.dataset.csrfToken;
    }

    // --- RENDER FUNCTIONS ---
    function renderConversations() {
        const sortedConvos = Array.from(conversations.values()).sort((a, b) => {
            const timeA = a.last_message ? new Date(a.last_message.timestamp) : new Date(a.created_at);
            const timeB = b.last_message ? new Date(b.last_message.timestamp) : new Date(b.created_at);
            return timeB - timeA;
        });

        if (sortedConvos.length === 0) {
            conversationListEl.innerHTML = `<div class="p-4 text-center text-base-content/60">No tienes conversaciones.</div>`;
            return;
        }
        conversationListEl.innerHTML = sortedConvos.map(convo => {
            const otherParticipant = convo.participants.find(p => p.id !== currentUserId) || convo.participants[0];
            const name = convo.is_group_chat ? convo.name : (otherParticipant ? `${otherParticipant.first_name} ${otherParticipant.last_name}` : "Usuario");
            const avatarUrl = otherParticipant?.foto || `/static/placeholder.png`;
            const lastMessage = convo.last_message ? `${convo.last_message.sender.first_name}: ${convo.last_message.content}` : 'No hay mensajes...';
            const unreadClass = convo.unread_count > 0 ? 'font-bold' : '';

            return `
                <div class="p-4 border-b hover:bg-base-200 cursor-pointer flex items-center ${activeConversationId === convo.id ? 'bg-base-300' : ''}" data-conversation-id="${convo.id}">
                    <div class="avatar mr-4"><div class="w-12 rounded-full"><img src="${avatarUrl}" /></div></div>
                    <div class="flex-grow overflow-hidden">
                        <div class="flex justify-between items-center">
                            <h4 class="truncate ${unreadClass}">${name}</h4>
                            ${convo.unread_count > 0 ? `<span class="badge badge-secondary badge-sm">${convo.unread_count}</span>` : ''}
                        </div>
                        <p class="text-sm text-base-content/60 truncate">${lastMessage}</p>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderMessages(messages) {
        if (!messages || messages.length === 0) {
            messageListEl.innerHTML = `<div class="p-4 text-center text-base-content/60">Inicia la conversación.</div>`;
            return;
        }
        messageListEl.innerHTML = messages.map(msg => {
            const isSender = msg.sender.id === currentUserId;
            return `
                <div class="chat ${isSender ? 'chat-end' : 'chat-start'}">
                    <div class="chat-image avatar"><div class="w-10 rounded-full"><img src="${msg.sender.foto || '/static/placeholder.png'}" /></div></div>
                    <div class="chat-header text-xs opacity-50 mb-1">${msg.sender.first_name} <time class="text-xs opacity-50">${new Date(msg.timestamp).toLocaleTimeString()}</time></div>
                    <div class="chat-bubble ${isSender ? 'chat-bubble-primary' : ''}">${msg.content}</div>
                </div>
            `;
        }).join('');
        messageListEl.scrollTop = messageListEl.scrollHeight;
    }

    function renderSelectedParticipants() {
        selectedParticipantsEl.innerHTML = '';
        selectedParticipants.forEach(user => {
            const tag = document.createElement('div');
            tag.className = 'badge badge-lg badge-outline gap-2';
            tag.innerHTML = `
                ${user.first_name} ${user.last_name}
                <button class="btn btn-xs btn-circle btn-ghost" data-user-id="${user.id}">&times;</button>
            `;
            selectedParticipantsEl.appendChild(tag);
        });
    }

    // --- API FUNCTIONS ---
    async function apiCall(url, options = {}) {
        options.headers = { ...options.headers, 'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/json' };
        const response = await fetch(url, options);
        if (!response.ok) throw new Error(`API call failed: ${response.statusText}`);
        return response.json();
    }

    async function fetchConversations() {
        try {
            const convosData = await apiCall('/api/chat/conversations/');
            conversations.clear();
            convosData.forEach(c => conversations.set(c.id, c));
            renderConversations();
        } catch (error) {
            console.error(error);
            conversationListEl.innerHTML = `<div class="p-4 text-center text-error">Error al cargar.</div>`;
        }
    }

    async function fetchMessages(conversationId) {
        try {
            const messages = await apiCall(`/api/chat/conversations/${conversationId}/messages/`);
            activeConversationMessages = messages;
            renderMessages(activeConversationMessages);
        } catch (error) {
            console.error(error);
            messageListEl.innerHTML = `<div class="p-4 text-center text-error">Error al cargar mensajes.</div>`;
        }
    }

    async function markAsRead(conversationId) {
        try {
            await apiCall(`/api/chat/conversations/${conversationId}/read/`, { method: 'POST' });
            const convo = conversations.get(conversationId);
            if (convo) {
                convo.unread_count = 0;
                renderConversations();
            }
        } catch (error) { console.error("Failed to mark as read:", error); }
    }

    // --- WEBSOCKET ---
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        chatSocket = new WebSocket(`${protocol}//${window.location.host}/ws/chat/`);

        chatSocket.onopen = () => {
            console.log("Chat WebSocket connected.");
            chatMessageInputEl.disabled = false;
            emojiBtn.disabled = false;
            chatFormEl.querySelector('button[type="submit"]').disabled = false;
            chatMessageInputEl.placeholder = "Escribe un mensaje...";
        };

        chatSocket.onclose = () => {
            console.error('Chat WebSocket closed. Reconnecting...');
            chatMessageInputEl.disabled = true;
            emojiBtn.disabled = true;
            chatFormEl.querySelector('button[type="submit"]').disabled = true;
            chatMessageInputEl.placeholder = "Reconectando...";
            setTimeout(connectWebSocket, 5000);
        };
        chatSocket.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === 'new_message') {
                const message = data.message;

                // If the message is from the current user, ignore it, as it was already added optimistically.
                if (message.sender.id === currentUser.id) {
                    // We might want to update the message ID from temporary to permanent,
                    // but for now, we'll just ignore the echo.
                    return;
                }

                const convo = conversations.get(parseInt(message.conversation));
                if (convo) {
                    convo.last_message = message;

                    // Asegurarse de que ambos IDs sean números enteros para la comparación
                    const messageConvId = parseInt(message.conversation);
                    const activeConvId = parseInt(activeConversationId);

                    if (messageConvId !== activeConvId) {
                        convo.unread_count = (convo.unread_count || 0) + 1;
                    } else {
                        activeConversationMessages.push(message);
                        renderMessages(activeConversationMessages);
                        markAsRead(activeConversationId);
                    }
                    renderConversations();
                } else {
                    // This case might happen if the user was just added to a conversation
                    // and a message arrives before the 'new_conversation' event.
                    // The 'new_conversation' event will handle adding it to the list.
                    fetchConversations();
                }
            } else if (data.type === 'new_conversation') {
                const newConvo = data.conversation;
                if (!conversations.has(newConvo.id)) {
                    conversations.set(newConvo.id, newConvo);
                    renderConversations();
                }
            }
        };
    }

    // --- EVENT HANDLERS ---
    async function selectConversation(id) {
        activeConversationId = id;
        renderConversations(); // Re-render to show active state

        chatPlaceholderEl.style.display = 'none';
        chatHeaderEl.style.display = 'flex';
        chatInputContainerEl.style.display = 'block';

        const convo = conversations.get(id);
        const otherParticipant = convo.participants.find(p => p.id !== currentUserId) || convo.participants[0];
        chatHeaderNameEl.textContent = convo.is_group_chat ? convo.name : `${otherParticipant.first_name} ${otherParticipant.last_name}`;
        chatHeaderAvatarEl.src = otherParticipant?.foto || `/static/placeholder.png`;
        chatHeaderParticipantsEl.textContent = convo.participants.map(p => p.first_name).join(', ');

        await fetchMessages(id);
        await markAsRead(id);
    }

    conversationListEl.addEventListener('click', (e) => {
        const conversationDiv = e.target.closest('[data-conversation-id]');
        if (conversationDiv) {
            selectConversation(parseInt(conversationDiv.dataset.conversationId));
        }
    });

    chatFormEl.addEventListener('submit', (e) => {
        e.preventDefault();
        const content = chatMessageInputEl.value.trim();
        if (content && activeConversationId && chatSocket) {
            // Send the message through the WebSocket
            chatSocket.send(JSON.stringify({
                'type': 'chat.new_message',
                'conversation_id': activeConversationId,
                'content': content
            }));

            // --- Optimistic UI Update ---
            // Create a temporary message object to display immediately.
            const optimisticMessage = {
                id: Date.now(), // Temporary ID
                conversation: activeConversationId,
                sender: {
                    id: currentUser.id,
                    first_name: currentUser.firstName,
                    foto: currentUser.photoUrl
                },
                content: content,
                timestamp: new Date().toISOString()
            };

            // Add to the message list and re-render
            activeConversationMessages.push(optimisticMessage);
            renderMessages(activeConversationMessages);

            // Update the conversation list's last message
            const convo = conversations.get(activeConversationId);
            if (convo) {
                convo.last_message = optimisticMessage;
                renderConversations();
            }

            // Clear the input field
            chatMessageInputEl.value = '';
        }
    });

    // Modal Logic
    newChatBtn.addEventListener('click', () => newChatModal.showModal());

    isGroupCheckbox.addEventListener('change', () => {
        groupNameContainer.style.display = isGroupCheckbox.checked ? 'block' : 'none';
    });

    userSearchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(async () => {
            const query = userSearchInput.value.trim();
            if (query.length < 2) {
                userSearchResultsEl.innerHTML = '';
                return;
            }
            const users = await apiCall(`/api/users/search/?q=${query}`);
            userSearchResultsEl.innerHTML = users.map(user => `
                <li><a data-user-id="${user.id}">${user.first_name} ${user.last_name} (${user.username})</a></li>
            `).join('');
        }, 300);
    });

    userSearchResultsEl.addEventListener('click', (e) => {
        const target = e.target.closest('[data-user-id]');
        if(target) {
            const userId = parseInt(target.dataset.userId);
            const userName = target.textContent;
            const [first_name, last_name] = userName.split(' ')[0];
            if (!selectedParticipants.has(userId)) {
                selectedParticipants.set(userId, {id: userId, first_name, last_name: userName.split(' ')[1]});
                renderSelectedParticipants();
            }
            userSearchInput.value = '';
            userSearchResultsEl.innerHTML = '';
        }
    });

    selectedParticipantsEl.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') {
            const userId = parseInt(e.target.dataset.userId);
            selectedParticipants.delete(userId);
            renderSelectedParticipants();
        }
    });

    startConversationBtn.addEventListener('click', async () => {
        const participant_ids = Array.from(selectedParticipants.keys());
        if (participant_ids.length === 0) return;

        const is_group_chat = isGroupCheckbox.checked;
        const name = groupNameInput.value.trim();

        if (is_group_chat && !name) {
            alert('Por favor, introduce un nombre para el grupo.');
            return;
        }

        try {
            const newConvo = await apiCall('/api/chat/conversations/', {
                method: 'POST',
                body: JSON.stringify({ participant_ids, is_group_chat, name })
            });
            conversations.set(newConvo.id, newConvo);
            selectConversation(newConvo.id);
            newChatModal.close();
            // Reset modal state
            selectedParticipants.clear();
            renderSelectedParticipants();
            userSearchInput.value = '';
            groupNameInput.value = '';
            isGroupCheckbox.checked = false;
            groupNameContainer.style.display = 'none';

        } catch (error) {
            console.error("Failed to create conversation", error);
            alert("Error al crear la conversación.");
        }
    });

    emojiBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        emojiPicker.style.display = emojiPicker.style.display === 'none' ? 'block' : 'none';
    });

    emojiPicker.addEventListener('emoji-click', event => {
        chatMessageInputEl.value += event.detail.emoji.unicode;
        emojiPicker.style.display = 'none';
    });

    // Ocultar el picker si se hace clic fuera
    document.addEventListener('click', (e) => {
        if (!emojiPicker.contains(e.target) && !emojiBtn.contains(e.target)) {
            emojiPicker.style.display = 'none';
        }
    });

    // --- INITIALIZATION ---
    function init() {
        // La obtención del CSRF token ahora se maneja en getCsrfToken().
        // Ya no es necesario crear un input oculto.
        fetchConversations();
        connectWebSocket();

        // Listen for the global event to refresh conversations
        document.addEventListener('globalchatmessage', fetchConversations);
    }

    init();
});
