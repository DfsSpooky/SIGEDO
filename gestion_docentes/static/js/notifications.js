document.addEventListener('DOMContentLoaded', function () {
    const notificationBadge = document.getElementById('notification-badge');
    const notificationList = document.getElementById('notification-list');
    const noNotificationsPlaceholder = document.getElementById('no-notifications-placeholder');

    if (!notificationBadge || !notificationList) return;

    let unreadCount = 0;

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    function updateBadge() {
        if (unreadCount > 0) {
            notificationBadge.textContent = unreadCount;
            notificationBadge.style.display = 'inline-flex';
        } else {
            notificationBadge.style.display = 'none';
        }
    }

    function addNotification(notification, prepend = false) {
        if (noNotificationsPlaceholder) {
            noNotificationsPlaceholder.style.display = 'none';
        }

        const notificationElement = document.createElement('div');
        notificationElement.id = `notification-${notification.id}`;
        notificationElement.classList.add('p-2', 'rounded-lg', 'hover:bg-base-200', 'transition-colors', 'duration-200', 'border-b', 'border-base-200/50');

        notificationElement.innerHTML = `
        <a href="${notification.url}" data-id="${notification.id}" class="notification-link flex items-start gap-3">
            <div class="mt-1">
                <span class="unread-dot w-2.5 h-2.5 rounded-full ${notification.leido ? 'bg-transparent' : 'bg-primary'} block"></span>
            </div>
            <div class="flex-1">
                <p class="text-sm">${notification.mensaje}</p>
                <p class="text-xs text-base-content/60 mt-1">${new Date(notification.fecha_creacion).toLocaleString()}</p>
            </div>
        </a>
    `;

        if (prepend) {
            notificationList.prepend(notificationElement);
        } else {
            notificationList.appendChild(notificationElement);
        }

        notificationElement.querySelector('.notification-link').addEventListener('click', function (e) {
            markAsRead(notification.id);
        });
    }

    function markAsRead(notificationId) {
        const notificationElement = document.getElementById(`notification-${notificationId}`);
        const unreadDot = notificationElement ? notificationElement.querySelector('.unread-dot') : null;

        if (unreadDot && unreadDot.classList.contains('bg-primary')) {
            fetch(`/api/notificaciones/${notificationId}/marcar-leida/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' },
            }).then(response => {
                if (response.ok) {
                    unreadDot.classList.remove('bg-primary');
                    unreadDot.classList.add('bg-transparent');
                    unreadCount = Math.max(0, unreadCount - 1);
                    updateBadge();
                }
            });
        }
    }

    function markAllAsRead() {
        fetch(`/api/notificaciones/marcar-todas-leidas/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' },
        }).then(response => {
            if (response.ok) {
                document.querySelectorAll('.unread-dot.bg-primary').forEach(dot => {
                    dot.classList.remove('bg-primary');
                    dot.classList.add('bg-transparent');
                });
                unreadCount = 0;
                updateBadge();
            }
        });
    }

    const markAllButton = document.createElement('button');
    markAllButton.className = 'btn btn-ghost btn-xs mt-2';
    markAllButton.textContent = 'Marcar todas como leídas';
    markAllButton.addEventListener('click', markAllAsRead);
    notificationList.parentElement.insertBefore(markAllButton, notificationList.nextSibling);

    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsPath = `${protocol}//${window.location.host}/ws/notifications/`;
        const notificationSocket = new WebSocket(wsPath);

        notificationSocket.onopen = function (e) { console.log("Notification WebSocket connected."); };
        notificationSocket.onclose = function (e) {
            console.error('Notification WebSocket closed. Reconnecting in 5s...');
            setTimeout(connect, 5000);
        };
        notificationSocket.onmessage = function (e) {
            const data = JSON.parse(e.data);
            if (data.type === 'send_notification') {
                addNotification(data.message, true);
                if (!data.message.leido) {
                    unreadCount++;
                    updateBadge();
                }
            }
        };
    }

    // Initial fetch
    const notificationsUrl = notificationList.dataset.url;
    if (notificationsUrl) {
        fetch(notificationsUrl)
            .then(response => response.json())
            .then(data => {
                if (data.notifications && data.notifications.length > 0) {
                    data.notifications.forEach(n => addNotification(n));
                }
                unreadCount = data.unread_count || 0;
                updateBadge();
            });
    }

    connect();
});
