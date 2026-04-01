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
            dateFormat: "H:i:S", // Format for Django backend
            altInput: true,
            altFormat: "h:i K", // Format for user
            time_24hr: false,
            allowInput: true,
        });

        // Initialize for datetime fields
        flatpickr('.vDateTimeField', {
            enableTime: true,
            dateFormat: "Y-m-d H:i:S", // Format for Django backend
            altInput: true,
            altFormat: "F j, Y h:i K", // Format for user
            time_24hr: false,
        });
    }
});
