document.addEventListener('DOMContentLoaded', function() {
    // This script replaces the default Django admin date/time widgets with flatpickr.

    if (typeof flatpickr !== 'undefined') {
        // Set the locale globally for all flatpickr instances
        flatpickr.localize(flatpickr.l10ns.es);

        // Initialize for date fields
        flatpickr('.vDateField', {
            dateFormat: "Y-m-d",
            altInput: true,
            altFormat: "F j, Y",
            allowInput: true, // Allows manual typing
        });

        // Initialize for time fields
        flatpickr('.vTimeField', {
            enableTime: true,
            noCalendar: true,
            dateFormat: "H:i:S",
            time_24hr: true,
            allowInput: true,
        });

        // Initialize for datetime fields
        flatpickr('.vDateTimeField', {
            enableTime: true,
            dateFormat: "Y-m-d H:i:S",
            altInput: true,
            altFormat: "F j, Y H:i",
            time_24hr: true,
        });
    }
});

function filterAdminTable() {
    const input = document.getElementById("admin-list-search");
    if (!input) return;

    const filter = input.value.toLowerCase();
    const table = document.getElementById("result_list");
    if (!table) return;

    const tbody = table.getElementsByTagName("tbody")[0];
    const tr = tbody.getElementsByTagName("tr");

    for (let i = 0; i < tr.length; i++) {
        let rowVisible = false;
        const tds = tr[i].getElementsByTagName("td");
        // Check all cells except the first one which is usually a checkbox
        for (let j = 1; j < tds.length; j++) {
            const td = tds[j];
            if (td && td.innerText.toLowerCase().indexOf(filter) > -1) {
                rowVisible = true;
                break;
            }
        }
        tr[i].style.display = rowVisible ? "" : "none";
    }
}

// --- WebSocket Notifications ---
// This logic will handle real-time updates for the notification bell.

document.addEventListener('DOMContentLoaded', function() {
    // Only attempt to connect if we are on a page with the notification bell,
    // which implies we are logged in as a staff user.
    if (document.getElementById('notification-badge') || document.querySelector('a[href*="core_notificacion_changelist"]')) {
        connectWebSocket();
    }
});

function connectWebSocket() {
    const protocol = window.location.protocol === 'https' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/notifications/`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = function(e) {
        console.log("Notification socket connected successfully.");
    };

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);

        if (data.type === 'send_notification') {
            const message = data.message;
            updateNotificationBadge();
            addNotificationToList(message);
            showToast(message.mensaje);
        }
    };

    socket.onclose = function(e) {
        console.error('Notification socket closed. Reconnecting in 5 seconds...');
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = function(err) {
        console.error('WebSocket error:', err.message, 'Closing socket.');
        socket.close(); // This will trigger the onclose event, which will attempt to reconnect.
    };
}

function updateNotificationBadge() {
    let badge = document.getElementById('notification-badge');
    if (badge) {
        badge.textContent = parseInt(badge.textContent || '0') + 1;
    } else {
        // If the badge doesn't exist (count was 0), we need to create it.
        const bellButton = document.querySelector('button > span.material-symbols-outlined');
        if (bellButton && bellButton.textContent.includes('notifications')) {
            const newBadge = document.createElement('span');
            newBadge.id = 'notification-badge';
            newBadge.className = 'absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white';
            newBadge.textContent = '1';
            bellButton.parentElement.appendChild(newBadge);
        }
    }
}

function addNotificationToList(notification) {
    const list = document.getElementById('notification-list');
    if (!list) return;

    // Remove the "empty" message if it's present
    const emptyMessage = list.querySelector('.empty-notification-message');
    if (emptyMessage) {
        emptyMessage.remove();
    }

    const newLink = document.createElement('a');
    newLink.href = notification.url;
    newLink.className = 'block p-4 text-sm hover:bg-gray-100 dark:hover:bg-gray-600';

    const messageP = document.createElement('p');
    messageP.className = 'font-medium text-gray-800 dark:text-gray-200';
    messageP.textContent = notification.mensaje;

    const timeP = document.createElement('p');
    timeP.className = 'text-xs text-gray-500 dark:text-gray-400';
    timeP.textContent = 'hace un momento'; // "just now"

    newLink.appendChild(messageP);
    newLink.appendChild(timeP);

    list.prepend(newLink);
}

function showToast(message) {
    // Create a container for toasts if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'fixed top-5 right-5 z-50 space-y-2';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = 'bg-blue-500 text-white py-3 px-5 rounded-lg shadow-lg transition-all duration-300 ease-in-out transform translate-x-full opacity-0';
    toast.innerHTML = `<p class="font-semibold">Nueva Notificación</p><p class="text-sm">${message}</p>`;

    toastContainer.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.remove('translate-x-full', 'opacity-0');
    });

    // Animate out and remove after 5 seconds
    setTimeout(() => {
        toast.classList.add('opacity-0');
        toast.addEventListener('transitionend', () => toast.remove());
    }, 5000);
}
