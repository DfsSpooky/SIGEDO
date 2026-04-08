// gestion_docentes/static/js/form_styles.js

document.addEventListener('DOMContentLoaded', function() {
    const floatingLabelInputs = document.querySelectorAll('.form-control-material');

    floatingLabelInputs.forEach(container => {
        const input = container.querySelector('input, textarea, select');
        const label = container.querySelector('label');

        if (input && label) {
            function updateLabel() {
                if (input.value.trim() !== '' || input.matches(':focus')) {
                    label.classList.add('active');
                } else {
                    label.classList.remove('active');
                }
            }

            input.addEventListener('focus', updateLabel);
            input.addEventListener('blur', updateLabel);
            input.addEventListener('input', updateLabel);

            // Initial check
            updateLabel();
        }
    });
});
