document.addEventListener('DOMContentLoaded', function() {
    // This script replaces the default Django admin date/time widgets with flatpickr.

    // Initialize for date fields
    if (typeof flatpickr !== 'undefined') {
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
            allowInput: true,
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
