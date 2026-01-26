document.addEventListener('DOMContentLoaded', function () {
    const DOMElements = {
        trash: document.querySelector('#trash-zone'),
        especialidad: document.querySelector('#especialidad'),
        semestre: document.querySelector('#semestre_cursado'),
    };

    let sortableInstances = [];

    function initializePlanner() {
        // Init Sortable on all drop zones
        const dropZones = document.querySelectorAll('.drop-zone');
        const unassignedZones = [
            document.getElementById('unassigned-generales'),
            document.getElementById('unassigned-especialidad')
        ].filter(el => el); // Filter nulls

        // Destroy existing instances to prevent duplicates or memory leaks
        sortableInstances.forEach(s => s.destroy());
        sortableInstances = [];

        const sharedConfig = {
            group: 'shared',
            animation: 150,
            onEnd: handleSortableEnd
        };

        // Grid Zones
        dropZones.forEach(zone => {
            sortableInstances.push(new Sortable(zone, sharedConfig));
        });

        // Unassigned Zones
        unassignedZones.forEach(zone => {
            sortableInstances.push(new Sortable(zone, {
                ...sharedConfig,
                sort: false
            }));
        });

        // Trash Zone (Static, likely already initialized but good to re-check if we destroy all)
        // Since trash zone is outside the HTMX swapped area (usually), we might not need to destroy/re-init it constantly.
        // However, if we clear `sortableInstances` global array, we lose the reference.
        // DOMElements.trash is static.
        if (DOMElements.trash) {
             // Check if already initialized?
             // Sortable doesn't expose a simple "isInitialized" on the element easily without keeping track.
             // But since we destroyed ALL instances in `sortableInstances`, we should re-init.
            sortableInstances.push(new Sortable(DOMElements.trash, {
                ...sharedConfig,
                onAdd: (evt) => {
                    handleTrashDrop(evt.item);
                }
            }));
        }
    }

    // Main Drag & Drop Handler
    function handleSortableEnd(evt) {
        const item = evt.item;
        const to = evt.to;
        const from = evt.from;

        // If dropped in same place, do nothing
        if (to === from) return;

        // If dropped in trash, handled by onAdd of trash
        if (to.id === 'trash-zone') return;

        // Target must be a valid drop zone
        if (!to.classList.contains('drop-zone')) {
            return;
        }

        const cursoId = item.dataset.cursoId;
        const bloqueId = item.dataset.bloqueId;
        const dia = to.dataset.dia;
        const franjaId = to.dataset.franjaId;
        const duracion = item.dataset.duracion;

        // Determine URL and payload
        let url = '/api/asignar-horario/';
        let vals = {
            curso_id: cursoId,
            dia: dia,
            franja_id: franjaId,
            duracion: duracion
        };

        if (bloqueId) {
            url = '/api/mover-bloque/';
            vals.bloque_id = bloqueId;
        }

        // Use HTMX to send request
        // target: to (the cell td) - response content will replace innerHTML of cell
        htmx.ajax('POST', url, {
            target: to,
            swap: 'innerHTML',
            values: vals
        }).then(() => {
            // Success handling if needed
        }).catch(err => {
            console.error("HTMX Error", err);
        });
    }

    function handleTrashDrop(item) {
        const bloqueId = item.dataset.bloqueId;
        if (!bloqueId) { item.remove(); return; } // Should not happen for unassigned items usually

        htmx.ajax('POST', '/api/desasignar-horario/', {
            values: { bloque_id: bloqueId },
            swap: 'none' // Don't swap trash content
        }).then(() => {
            item.remove();
            // Optional: Reload unassigned list?
        });
    }

    // Global function to confirm delete (called from partial onclick)
    window.confirmDelete = function (bloqueId) {
        Swal.fire({
            title: '¿Eliminar este bloque?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'No'
        }).then((result) => {
            if (result.isConfirmed) {
                htmx.ajax('POST', '/api/desasignar-horario/', {
                    values: { bloque_id: bloqueId },
                    swap: 'none'
                }).then(() => {
                    const el = document.querySelector(`[data-bloque-id="${bloqueId}"]`);
                    if (el) el.remove();
                });
            }
        });
    };

    // Re-init on HTMX swaps
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        // Only re-init if the swap happened in the planner main container or relevant sub-parts
        if (evt.target.id === 'planner-main-container' || evt.target.classList.contains('tab-pane') || evt.target.closest('#planner-main-container')) {
             initializePlanner();
        }
    });

    // Initial load (in case content is already there, though unlikely with current setup)
    initializePlanner();
});
