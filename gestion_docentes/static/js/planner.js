document.addEventListener('DOMContentLoaded', function () {
    // --- INITIALIZATION & CONFIGURATION ---
    // These variables should be defined in a global config object in the HTML before loading this script.
    // e.g., window.PlannerConfig = { franjasManana: [...], franjasTarde: [...], diasSemana: [...], csrfToken: "..." };

    const config = window.PlannerConfig || {};
    const franjasManana = config.franjasManana || [];
    const franjasTarde = config.franjasTarde || [];
    const diasSemana = config.diasSemana || [];
    const csrfToken = config.csrfToken || '';

    if (!config.franjasManana) {
        console.error("PlannerConfig not found or incomplete. Make sure to define window.PlannerConfig in the template.");
        return;
    }

    const selectors = {
        especialidad: '#especialidad',
        semestre: '#semestre_cursado',
        plannerBody: '#planner-body',
        placeholder: '#planner-placeholder',
        gridManana: '#schedule-grid-manana',
        gridTarde: '#schedule-grid-tarde',
        unassignedContainer: '#unassigned-courses-container',
        trash: '#trash-zone',
        searchInput: '#course-search-input',
        autoAssignBtn: '#auto-assign-btn',
        autoAssignLog: '#auto-assign-log',
        sidebarTabs: '.planner-sidebar .tabs .tab',
        scheduleTabsContainer: '#schedule-tabs-container',
        globalAutoAssignBtn: '#global-auto-assign-btn'
    };

    const DOMElements = Object.fromEntries(
        Object.entries(selectors).map(([key, selector]) => [key, document.querySelector(selector)])
    );

    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true
    });

    // --- API & UTILITY FUNCTIONS ---
    async function callApi(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        };
        if (body) options.body = JSON.stringify(body);
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || data.error || 'Error en el servidor');
        return data;
    }

    function log(message) {
        if (!DOMElements.autoAssignLog) return;
        DOMElements.autoAssignLog.innerHTML += `<div>[${new Date().toLocaleTimeString()}] ${message}</div>`;
        DOMElements.autoAssignLog.scrollTop = DOMElements.autoAssignLog.scrollHeight;
    }

    // --- RENDERING FUNCTIONS ---
    function createCourseElement(curso, isAssigned = false) {
        const div = document.createElement('div');
        div.className = `relative p-2 rounded-lg text-sm transition-all duration-300 cursor-grab active:cursor-grabbing border h-full flex flex-col`;

        let cellClasses = '';

        if (isAssigned) {
            div.classList.add('group', 'assigned-course-item');
            div.dataset.bloqueId = curso.bloque_id;
            div.dataset.cursoId = curso.curso_id;
            div.dataset.duracion = curso.duracion_bloques;
            div.dataset.fullData = JSON.stringify(curso);
            div.dataset.courseType = curso.tipo_curso;

            let icon = '';
            if (curso.tipo_curso === 'GENERAL') {
                cellClasses = 'cell-general';
                icon = '<i class="fas fa-globe-americas fa-fw mr-2"></i>';
            } else {
                cellClasses = 'cell-especialidad';
                icon = '<i class="fas fa-graduation-cap fa-fw mr-2"></i>';
            }

            const allFranjas = [...franjasManana, ...franjasTarde];
            const startFranjaIndex = allFranjas.findIndex(f => f.id === curso.franja_id_inicio);
            let timeText = '';
            if (startFranjaIndex !== -1) {
                const endFranjaIndex = startFranjaIndex + curso.duracion_bloques - 1;
                if (endFranjaIndex < allFranjas.length) {
                    timeText = `${allFranjas[startFranjaIndex].hora_inicio.slice(0,5)} - ${allFranjas[endFranjaIndex].hora_fin.slice(0,5)}`;
                }
            }

            div.innerHTML = `
                <div class="flex-grow">
                    <p class="font-bold truncate pr-4">${curso.nombre}</p>
                    <p class="text-xs opacity-70 truncate">${curso.docente_nombre}</p>
                </div>
                <div class="mt-2 text-xs opacity-80">
                    <div class="flex items-center">${icon} ${curso.tipo_curso}</div>
                    <div class="font-mono mt-1"><i class="far fa-clock fa-fw mr-2 opacity-60"></i>${timeText} (${curso.duracion_bloques}h)</div>
                </div>
            `;

            const controlsDiv = document.createElement('div');
            controlsDiv.className = 'absolute top-1 right-1 flex flex-col items-center space-y-1 opacity-0 group-hover:opacity-100 transition-opacity';
            const createControlButton = (iconClass, colorClass, title, onClick) => {
                const button = document.createElement('button');
                button.className = `btn btn-xs btn-square bg-base-100/50 backdrop-blur-sm border-0 text-${colorClass}/80 hover:bg-base-100 hover:text-${colorClass}`;
                button.innerHTML = `<i class="fas ${iconClass}"></i>`;
                button.title = title;
                button.addEventListener('click', (e) => { e.stopPropagation(); onClick(e); });
                return button;
            };
            controlsDiv.appendChild(createControlButton('fa-plus', 'success', 'Aumentar duración', () => handleDurationChange(div.dataset.bloqueId, 'increase')));
            controlsDiv.appendChild(createControlButton('fa-minus', 'warning', 'Disminuir duración', () => handleDurationChange(div.dataset.bloqueId, 'decrease')));
            controlsDiv.appendChild(createControlButton('fa-times', 'error', 'Eliminar bloque', () => {
                Swal.fire({
                    title: '¿Eliminar este bloque?', text: `Se eliminará el bloque de ${curso.duracion_bloques} hora(s) para "${curso.nombre}".`,
                    icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, eliminar', cancelButtonText: 'No'
                }).then(result => result.isConfirmed && handleDeassign(div));
            }));
            div.appendChild(controlsDiv);
        } else {
            div.dataset.cursoId = curso.id;
            div.dataset.fullData = JSON.stringify(curso);
            div.dataset.duracion = Math.min(2, curso.horas_pendientes);
            div.classList.add('unassigned-course-item');
            div.innerHTML = `
                <p class="course-name">${curso.nombre}</p>
                <p class="course-teacher">${curso.docente_nombre}</p>
                <p class="course-pending-hours">${curso.horas_pendientes} de ${curso.horas_totales}h pendientes</p>
            `;
        }
        return { element: div, cellClasses: cellClasses.split(' ') };
    }

    function renderPlanner(plannerData) {
        const renderGrid = (container, franjas) => {
            container.innerHTML = '';
            franjas.forEach(franja => {
                const row = document.createElement('tr');
                row.innerHTML = `<td class="text-center text-xs font-medium text-base-content/60 align-top h-24 p-1 border-r border-base-300">${franja.hora_inicio.slice(0,5)} - ${franja.hora_fin.slice(0,5)}</td>`;
                diasSemana.forEach(dia => {
                    row.innerHTML += `<td class="p-1 border-t border-r border-base-300 align-top relative drop-zone transition-colors duration-300" data-dia="${dia}" data-franja-id="${franja.id}"></td>`;
                });
                container.appendChild(row);
            });
        };
        renderGrid(DOMElements.gridManana, franjasManana);
        renderGrid(DOMElements.gridTarde, franjasTarde);

        DOMElements.unassignedContainer.innerHTML = '';
        const { generales, especialidad } = plannerData.cursos_pendientes;
        const createAccordion = (title, courses, id) => {
            const collapseDiv = document.createElement('div');
            collapseDiv.className = 'collapse collapse-arrow bg-base-200/50';
            collapseDiv.innerHTML = `<input type="checkbox" checked /><div class="collapse-title text-md font-medium">${title} (${courses.length})</div><div class="collapse-content"><div id="${id}" class="space-y-2 pt-2"></div></div>`;
            const courseList = collapseDiv.querySelector(`#${id}`);
            if (courses.length > 0) {
                courses.forEach(curso => courseList.appendChild(createCourseElement(curso, false).element));
            } else {
                courseList.innerHTML = '<p class="text-xs text-base-content/50 p-2">No hay cursos pendientes.</p>';
            }
            return collapseDiv;
        };
        DOMElements.unassignedContainer.appendChild(createAccordion('Generales Pendientes', generales, 'unassigned-generales'));
        DOMElements.unassignedContainer.appendChild(createAccordion('Especialidad Pendientes', especialidad, 'unassigned-especialidad'));

        plannerData.cursos_asignados.forEach(bloque => {
            if (!bloque.franja_id_inicio) return;
            const cell = document.querySelector(`td[data-dia="${bloque.dia}"][data-franja-id="${bloque.franja_id_inicio}"]`);
            if (cell) {
                const { element, cellClasses } = createCourseElement(bloque, true);
                cell.appendChild(element);
                cell.classList.add(...cellClasses);

                if (bloque.duracion_bloques > 1) {
                    applyVisualSpan(cell, bloque.duracion_bloques, cellClasses);
                }
            }
        });
        initializeDragAndDrop();
    }

    // --- DRAG AND DROP LOGIC ---
    let sortableInstances = [];
    function initializeDragAndDrop() {
        sortableInstances.forEach(s => s.destroy());
        sortableInstances = [];
        const sharedConfig = { group: 'shared', animation: 150 };

        const onAdd = async (evt) => {
            const { item, to, from } = evt;
            revertVisualSpan(from);

            const cursoData = JSON.parse(item.dataset.fullData);
            const targetFranjaId = parseInt(to.dataset.franjaId, 10);

            const isTarde = franjasTarde.some(f => f.id === targetFranjaId);
            const targetTurno = isTarde ? 'TARDE' : 'MANANA';

            // Regla 1: Semestres 1-4 solo mañana (salvo excepción)
            if (cursoData.semestre_cursado <= 4 && targetTurno === 'TARDE' && !cursoData.excepcion_horario) {
                Toast.fire({ icon: 'error', title: 'Horario no permitido', text: 'Los cursos de semestres inferiores solo pueden llevarse en el turno de mañana.' });
                await loadPlannerData();
                return;
            }

            // Regla 2: Semestres 5-10 solo tarde
            if (cursoData.semestre_cursado >= 5 && targetTurno === 'MANANA') {
                Toast.fire({ icon: 'error', title: 'Horario no permitido', text: 'Los cursos de semestres superiores solo pueden llevarse en el turno de tarde.' });
                await loadPlannerData();
                return;
            }

            if (to.classList.contains('conflict-cell') || to.querySelector('[data-bloque-id]')) {
                Toast.fire({ icon: 'error', title: 'No se puede asignar en este espacio ocupado o en conflicto.' });
                await loadPlannerData();
                return;
            }

            try {
                const isExistingBlock = item.dataset.bloqueId;
                const payload = isExistingBlock ? {
                    bloque_id: item.dataset.bloqueId,
                    dia: to.dataset.dia,
                    franja_id: to.dataset.franjaId,
                } : {
                    curso_id: item.dataset.cursoId,
                    dia: to.dataset.dia,
                    franja_id: to.dataset.franjaId,
                    duracion: parseInt(item.dataset.duracion, 10)
                };
                const url = isExistingBlock ? '/api/mover-bloque/' : '/api/asignar-horario/';
                const data = await callApi(url, 'POST', payload);
                Toast.fire({ icon: 'success', title: data.message });
                await loadPlannerData();
            } catch (error) {
                Toast.fire({ icon: 'error', title: `Error: ${error.message}` });
                await loadPlannerData();
            }
        };

        const onStart = (evt) => highlightConflicts(evt.item);
        const onEnd = () => clearConflicts();
        sortableInstances.push(new Sortable(document.getElementById('unassigned-generales'), sharedConfig));
        sortableInstances.push(new Sortable(document.getElementById('unassigned-especialidad'), sharedConfig));
        document.querySelectorAll('.drop-zone').forEach(zone => sortableInstances.push(new Sortable(zone, { ...sharedConfig, onAdd, onStart, onEnd })));
        sortableInstances.push(new Sortable(DOMElements.trash, { ...sharedConfig, onAdd: (evt) => handleDeassign(evt.item) }));
    }

    async function handleDeassign(courseElement) {
        const bloqueId = courseElement.dataset.bloqueId;
        if (!bloqueId) {
            courseElement.remove();
            return;
        }

        const fromCell = courseElement.parentElement;
        if (fromCell && fromCell.classList.contains('drop-zone')) {
            revertVisualSpan(fromCell);
        }

        try {
            await callApi('/api/desasignar-horario/', 'POST', { bloque_id: bloqueId });
            Toast.fire({ icon: 'info', title: 'Bloque de horario eliminado' });
            courseElement.remove();
            await loadPlannerData();
        } catch (error) {
            Toast.fire({ icon: 'error', title: `Error al eliminar: ${error.message}` });
            await loadPlannerData();
        }
    }

    // --- HELPER FUNCTIONS ---
    function getCellColorClasses(cell) {
        return Array.from(cell.classList).filter(c => c.startsWith('bg-'));
    }

    function applyVisualSpan(cell, duration, colorClasses) {
        if (!cell || duration < 2) return;
        cell.setAttribute('rowspan', duration);
        let currentRow = cell.parentElement;
        for (let i = 1; i < duration; i++) {
            currentRow = currentRow.nextElementSibling;
            if (currentRow) {
                const cellToModify = currentRow.querySelector(`[data-dia="${cell.dataset.dia}"]`);
                if (cellToModify) {
                    cellToModify.style.display = 'none';
                    cellToModify.classList.add(...colorClasses);
                }
            }
        }
    }

    function revertVisualSpan(cell) {
        if (!cell) return;
        const duration = parseInt(cell.getAttribute('rowspan') || '1', 10);
        const colorClasses = getCellColorClasses(cell);
        cell.classList.remove(...colorClasses);
        cell.setAttribute('rowspan', 1);

        if (duration > 1) {
            let currentRow = cell.parentElement;
            for (let i = 1; i < duration; i++) {
                currentRow = currentRow.nextElementSibling;
                if (currentRow) {
                    const cellToShow = currentRow.querySelector(`[data-dia="${cell.dataset.dia}"]`);
                    if (cellToShow) {
                        cellToShow.style.display = '';
                        cellToShow.classList.remove(...colorClasses);
                    }
                }
            }
        }
    }

    // --- CONFLICTS & DURATION ---
    async function highlightConflicts(item) {
        clearConflicts();
        const cursoId = item.dataset.cursoId;
        const data = await callApi(`/api/get-teacher-conflicts/?curso_id=${cursoId}`);
        if (data.data && data.data.conflicts) {
             // Adaptado para la respuesta nueva de DRF { status: 'success', data: { conflicts: [...] } }
             // Ojo: en la versión anterior era data.conflicts.
            data.data.conflicts.forEach(c => {
                const cell = document.querySelector(`td[data-dia="${c.dia}"][data-franja-id="${c.franja_id}"]`);
                if (cell) {
                    cell.classList.add('conflict-cell');
                    cell.setAttribute('title', c.razon);
                }
            });
        }
    }
    function clearConflicts() {
        document.querySelectorAll('.conflict-cell').forEach(c => {
            c.classList.remove('conflict-cell');
            c.removeAttribute('title');
        });
    }
    async function handleDurationChange(bloqueId, action) {
        try {
            const payload = { bloque_id: bloqueId, accion: action };
            const data = await callApi('/api/ajustar-duracion/', 'POST', payload);
            Toast.fire({ icon: 'success', title: data.message });
            await loadPlannerData();
        } catch (error) {
            Toast.fire({ icon: 'error', title: `Error: ${error.message}` });
        }
    }

    // --- EVENT HANDLERS & INITIALIZATION ---
    async function loadPlannerData() {
        const especialidadId = DOMElements.especialidad.value;
        const semestreNum = DOMElements.semestre.value;
        if (!especialidadId || !semestreNum) {
            DOMElements.plannerBody.classList.add('hidden');
            DOMElements.placeholder.classList.remove('hidden');
            return;
        }
        DOMElements.plannerBody.classList.remove('hidden');
        DOMElements.placeholder.classList.add('hidden');
        const skeletonRow = `<tr><td colspan="${diasSemana.length + 1}"><div class="skeleton-loader h-48 w-full"></div></td></tr>`;
        DOMElements.gridManana.innerHTML = skeletonRow;
        DOMElements.gridTarde.innerHTML = skeletonRow;
        DOMElements.unassignedContainer.innerHTML = '<div class="skeleton-loader h-16 w-full"></div>';
        try {
            const response = await callApi(`/api/get-cursos-no-asignados/?especialidad_id=${especialidadId}&semestre_cursado=${semestreNum}`);
            if (response.status === 'success') {
                renderPlanner(response.data);
            } else { throw new Error(response.message || 'El servidor devolvió una respuesta inesperada.'); }
        } catch (error) {
            Swal.fire({ icon: 'error', title: 'Error al cargar datos', text: error.message });
        }
    }

    async function handleAutoAssign() {
        const especialidadId = DOMElements.especialidad.value;
        const semestreNum = DOMElements.semestre.value;
        if (!especialidadId || !semestreNum) return Toast.fire({ icon: 'warning', title: 'Selecciona especialidad y semestre primero.' });
        DOMElements.autoAssignBtn.classList.add('btn-disabled', 'loading');
        log('Iniciando proceso de asignación automática...');
        try {
            const data = await callApi('/api/auto-asignar/', 'POST', { especialidad_id: especialidadId, semestre_cursado: semestreNum });
            log(data.message);
            log('Actualizando la interfaz...');
            renderPlanner(data.data.plannerData); // Adaptado para la respuesta de DRF
            Toast.fire({ icon: 'success', title: 'Proceso completado!' });
        } catch (error) {
            log(`ERROR: ${error.message}`);
            Swal.fire({ icon: 'error', title: 'Error en Auto-Asignación', text: error.message });
        } finally {
            DOMElements.autoAssignBtn.classList.remove('btn-disabled', 'loading');
        }
    }

    async function handleGlobalAutoAssign() {
        Swal.fire({
            title: '¿Generar Horario Global?',
            text: "¡Atención! Esta acción borrará y regenerará TODOS los horarios para el semestre activo. Este proceso puede tardar unos minutos y no se puede deshacer.",
            icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, ¡generar ahora!', cancelButtonText: 'Cancelar', reverseButtons: true
        }).then(async (result) => {
            if (result.isConfirmed) {
                const btn = DOMElements.globalAutoAssignBtn;
                btn.classList.add('loading', 'btn-disabled');
                Swal.fire({ title: 'Procesando...', text: 'Generando horarios. Por favor, espera.', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
                try {
                    const data = await callApi('/api/generar-horario-automatico/', 'POST');
                    Swal.close();
                    Swal.fire({ title: '¡Proceso Finalizado!', text: data.message, icon: 'success' });
                    loadPlannerData();
                } catch (error) {
                    Swal.fire({ title: 'Error', text: `Ocurrió un error: ${error.message}`, icon: 'error' });
                } finally {
                    btn.classList.remove('loading', 'btn-disabled');
                }
            }
        });
    }

    // --- EVENT LISTENERS ---
    if (DOMElements.especialidad) DOMElements.especialidad.addEventListener('change', loadPlannerData);
    if (DOMElements.semestre) DOMElements.semestre.addEventListener('change', loadPlannerData);
    if (DOMElements.autoAssignBtn) DOMElements.autoAssignBtn.addEventListener('click', handleAutoAssign);
    if (DOMElements.globalAutoAssignBtn) DOMElements.globalAutoAssignBtn.addEventListener('click', handleGlobalAutoAssign);
    if (DOMElements.searchInput) {
        DOMElements.searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            document.querySelectorAll('#unassigned-courses-container > .collapse .p-2.rounded-lg').forEach(card => {
                card.style.display = card.textContent.toLowerCase().includes(searchTerm) ? '' : 'none';
            });
        });
    }

    // Logic for Sidebar Tabs (Manual/Auto)
    const sidebarTabs = document.querySelectorAll(selectors.sidebarTabs);
    sidebarTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            sidebarTabs.forEach(t => t.classList.remove('tab-active'));
            tab.classList.add('tab-active');

            document.querySelectorAll('#tab-manual, #tab-auto').forEach(c => c.classList.remove('active'));
            const target = document.getElementById(`tab-${tab.dataset.tab}`);
            if(target) target.classList.add('active');
        });
    });

    // Logic for Schedule Tabs (Mañana/Tarde)
    if (DOMElements.scheduleTabsContainer) {
        DOMElements.scheduleTabsContainer.addEventListener('click', (e) => {
            if (e.target.matches('.tab')) {
                e.preventDefault();

                DOMElements.scheduleTabsContainer.querySelectorAll('.tab').forEach(tab => tab.classList.remove('tab-active'));
                e.target.classList.add('tab-active');

                document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
                const targetPane = document.querySelector(e.target.dataset.tabTarget);
                if (targetPane) {
                    targetPane.classList.add('active');
                }
            }
        });
    }

    // Initial Load
    if (DOMElements.especialidad && DOMElements.especialidad.value && DOMElements.semestre && DOMElements.semestre.value) {
        loadPlannerData();
    }
});
