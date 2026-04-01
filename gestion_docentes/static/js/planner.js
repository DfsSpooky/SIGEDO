document.addEventListener('DOMContentLoaded', function () {

    let currentPlannerData = null;
    const WEEK_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'];

    // --- API & UTILITY FUNCTIONS ---
    async function callApi(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.PlannerConfig.csrfToken
            }
        };
        if (body) options.body = JSON.stringify(body);
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || data.error || 'Error en el servidor');
        return data;
    }

    const DOMElements = {
        especialidad: document.querySelector('#especialidad'),
        semestre: document.querySelector('#semestre_cursado'),
        plannerBody: document.querySelector('#planner-body'),
        placeholder: document.querySelector('#planner-placeholder'),
        gridManana: document.querySelector('#schedule-grid-manana'),
        gridTarde: document.querySelector('#schedule-grid-tarde'),
        unassignedContainer: document.querySelector('#unassigned-courses-container'),
        trash: document.querySelector('#trash-zone'),
        searchInput: document.querySelector('#course-search-input'),
        autoAssignBtn: document.querySelector('#auto-assign-btn'),
        autoAssignLog: document.querySelector('#auto-assign-log'),
        groupAutoAssignBtn: document.querySelector('#group-auto-assign-btn'),
        globalAutoAssignBtn: document.querySelector('#global-auto-assign-btn'),
        clearScheduleBtn: document.querySelector('#clear-schedule-btn'),
        scheduleTabsContainer: document.querySelector('#schedule-tabs-container'),
        toggleGeneralEdit: document.querySelector('#toggle-general-edit')
    };

    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });

    function log(message) {
        if (!DOMElements.autoAssignLog) return;
        DOMElements.autoAssignLog.innerHTML += `<div>[${new Date().toLocaleTimeString()}] ${message}</div>`;
        DOMElements.autoAssignLog.scrollTop = DOMElements.autoAssignLog.scrollHeight;
    }

    // --- RENDERING FUNCTIONS ---
    function createCourseElement(curso, isAssigned = false) {
        const div = document.createElement('div');
        div.className = `relative p-2 rounded-lg text-sm transition-all duration-300 border h-full flex flex-col`;

        let blockClasses = '';
        let cellClasses = '';

        if (isAssigned) {
            div.classList.add('group', 'assigned-course-item');

            // Lógica de Ghost Blocks
            const allowEdit = DOMElements.toggleGeneralEdit ? DOMElements.toggleGeneralEdit.checked : false;
            const isGhost = curso.tipo_curso === 'GENERAL' && !allowEdit;

            div.dataset.bloqueId = curso.bloque_id;
            div.dataset.cursoId = curso.curso_id;
            div.dataset.duracion = curso.duracion_bloques;
            div.dataset.fullData = JSON.stringify(curso);
            div.dataset.courseType = curso.tipo_curso;

            let icon = '';

            if (isGhost) {
                cellClasses = 'bg-base-300 text-base-content/60 border-base-300 cursor-not-allowed';
                icon = '<i class="fas fa-lock fa-fw mr-2 opacity-50"></i>';
                div.classList.add('static-course');
            } else {
                div.classList.add('cursor-grab', 'active:cursor-grabbing');
                if (curso.tipo_curso === 'GENERAL') {
                    cellClasses = 'cell-general';
                    icon = '<i class="fas fa-globe-americas fa-fw mr-2"></i>';
                } else {
                    cellClasses = 'cell-especialidad';
                    icon = '<i class="fas fa-graduation-cap fa-fw mr-2"></i>';
                }
            }

            const allFranjas = [...window.PlannerConfig.franjasManana, ...window.PlannerConfig.franjasTarde];
            const startFranjaIndex = allFranjas.findIndex(f => f.id === curso.franja_id_inicio);
            let timeText = '';
            if (startFranjaIndex !== -1) {
                const endFranjaIndex = startFranjaIndex + curso.duracion_bloques - 1;
                if (endFranjaIndex < allFranjas.length) {
                    timeText = `${allFranjas[startFranjaIndex].hora_inicio.slice(0, 5)} - ${allFranjas[endFranjaIndex].hora_fin.slice(0, 5)}`;
                }
            }

            let sharedBadge = '';
            if (curso.especialidades_nombres && curso.especialidades_nombres.length > 1) {
                const titleText = curso.especialidades_nombres.join(', ');
                sharedBadge = `<span class="badge badge-xs badge-info ml-1" title="${titleText}" style="cursor: help;">+${curso.especialidades_nombres.length - 1}</span>`;
            }

            div.innerHTML = `
                <div class="flex-grow">
                    <p class="font-bold truncate pr-4" title="${curso.nombre}">${curso.nombre}</p>
                    <p class="text-xs opacity-70 truncate">${curso.docente_nombre}</p>
                </div>
                <div class="mt-2 text-xs opacity-80">
                    <div class="flex items-center">
                        ${icon} ${curso.tipo_curso}
                        ${sharedBadge}
                    </div>
                    <div class="font-mono mt-1"><i class="far fa-clock fa-fw mr-2 opacity-60"></i>${timeText} (${curso.duracion_bloques}h)</div>
                </div>
            `;

            if (!isGhost) {
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
            }

        } else {
            // --- Cursos NO asignados (Lista Lateral) ---
            div.dataset.cursoId = curso.id;
            div.dataset.fullData = JSON.stringify(curso);
            div.dataset.duracion = Math.min(2, curso.horas_pendientes);
            div.classList.add('unassigned-course-item', 'cursor-grab', 'active:cursor-grabbing');

            let sharedBadge = '';
            if (curso.especialidades_nombres && curso.especialidades_nombres.length > 1) {
                const titleText = curso.especialidades_nombres.join(', ');
                sharedBadge = `<span class="badge badge-xs badge-ghost ml-1 border-base-300" title="${titleText}" style="cursor: help;">+${curso.especialidades_nombres.length - 1}</span>`;
            }

            // 1. LÓGICA DE BARRA DE PROGRESO
            // Calculamos porcentaje usando horas_asignadas (que viene del backend nuevo)
            const assigned = curso.horas_asignadas || 0;
            const total = curso.horas_totales || 0;
            const percent = total > 0 ? Math.round((assigned / total) * 100) : 0;

            let progressColor = 'progress-error'; // Rojo (poco avance)
            let textColor = 'text-error';

            if (percent >= 100) {
                progressColor = 'progress-success'; // Verde
                textColor = 'text-success';
            } else if (percent >= 50) {
                progressColor = 'progress-warning'; // Amarillo
                textColor = 'text-warning';
            }

            div.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <p class="course-name truncate pr-1" title="${curso.nombre}">${curso.nombre}</p>
                    ${sharedBadge}
                </div>
                <p class="course-teacher truncate mb-2">${curso.docente_nombre}</p>
                
                <div class="w-full">
                    <div class="flex justify-between text-[10px] font-bold ${textColor} mb-0.5">
                        <span>${curso.horas_pendientes}h pendientes</span>
                        <span>${percent}%</span>
                    </div>
                    <progress class="progress ${progressColor} w-full h-1.5 bg-base-300" value="${assigned}" max="${total}"></progress>
                </div>
            `;
        }
        return { element: div, cellClasses: cellClasses ? cellClasses.split(' ') : [] };
    }

    function renderPlanner(plannerData) {
        const renderGrid = (container, franjas) => {
            container.innerHTML = '';
            franjas.forEach(franja => {
                const row = document.createElement('tr');
                row.innerHTML = `<td class="text-center text-xs font-medium text-base-content/60 align-top h-24 p-1 border-r border-base-300">${franja.hora_inicio.slice(0, 5)} - ${franja.hora_fin.slice(0, 5)}</td>`;
                window.PlannerConfig.diasSemana.forEach(dia => {
                    row.innerHTML += `<td class="p-1 border-t border-r border-base-300 align-top relative drop-zone transition-colors duration-300" data-dia="${dia}" data-franja-id="${franja.id}"></td>`;
                });
                container.appendChild(row);
            });
        };
        renderGrid(DOMElements.gridManana, window.PlannerConfig.franjasManana);
        renderGrid(DOMElements.gridTarde, window.PlannerConfig.franjasTarde);

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
                if (cellClasses.length) cell.classList.add(...cellClasses);

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

        const sharedConfig = {
            group: 'shared',
            animation: 150,
            filter: '.static-course',
            onMove: function (evt) {
                return !evt.related.classList.contains('static-course');
            }
        };

        const onAdd = async (evt) => {
            const { item, to, from } = evt;
            revertVisualSpan(from);

            // Validaciones
            const cursoData = JSON.parse(item.dataset.fullData);
            const targetFranjaId = parseInt(to.dataset.franjaId, 10);
            const isTarde = window.PlannerConfig.franjasTarde.some(f => f.id === targetFranjaId);
            const targetTurno = isTarde ? 'TARDE' : 'MANANA';

            if (cursoData.semestre_cursado <= 4 && targetTurno === 'TARDE' && !cursoData.excepcion_horario) {
                Toast.fire({ icon: 'error', title: 'Horario no permitido', text: 'Semestres 1-4 solo en turno mañana.' });
                await loadPlannerData();
                return;
            }
            if (cursoData.semestre_cursado >= 5 && targetTurno === 'MANANA') {
                Toast.fire({ icon: 'error', title: 'Horario no permitido', text: 'Semestres 5-10 solo en turno tarde.' });
                await loadPlannerData();
                return;
            }

            const existingBlock = Array.from(to.querySelectorAll('[data-bloque-id]')).find(el => el !== item);
            if (to.classList.contains('conflict-cell') || existingBlock) {
                Toast.fire({ icon: 'error', title: 'Espacio ocupado o en conflicto.' });
                await loadPlannerData();
                return;
            }

            // 2. VALIDACIÓN DE FATIGA DOCENTE (CLIENT-SIDE)
            checkTeacherFatigue(to, cursoData);

            try {
                const isExistingBlock = item.dataset.bloqueId;

                let durationToAssign = parseInt(item.dataset.duracion, 10);
                let finalCursoData = null;

                if (!isExistingBlock) {
                    try {
                        finalCursoData = JSON.parse(item.dataset.fullData);
                    } catch (e) { console.error(e); }

                    if (finalCursoData && finalCursoData.horas_pendientes > 1) {
                        const { value: selectedDur } = await Swal.fire({
                            title: 'Asignar Horas',
                            text: `¿Cuántas horas seguidas quieres asignar para "${finalCursoData.nombre}"? (Máx. ${finalCursoData.horas_pendientes})`,
                            input: 'number',
                            inputValue: Math.min(2, finalCursoData.horas_pendientes),
                            showCancelButton: true,
                            inputValidator: (value) => {
                                if (!value || value < 1) return 'Debes asignar al menos 1 hora.';
                                if (value > finalCursoData.horas_pendientes) return `No puedes asignar más de ${finalCursoData.horas_pendientes} horas pendientes.`;
                            }
                        });

                        if (!selectedDur) { // User cancelled
                            revertVisualSpan(from); // Just reload state
                            await loadPlannerData();
                            return;
                        }

                        durationToAssign = parseInt(selectedDur, 10);
                    } else if (finalCursoData && finalCursoData.horas_pendientes === 1) {
                        durationToAssign = 1;
                    }
                }

                const payload = isExistingBlock ? {
                    bloque_id: item.dataset.bloqueId,
                    dia: to.dataset.dia,
                    franja_id: to.dataset.franjaId,
                } : {
                    curso_id: item.dataset.cursoId,
                    dia: to.dataset.dia,
                    franja_id: to.dataset.franjaId,
                    duracion: durationToAssign
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

        const onStart = (evt) => showSuggestionsAndConflicts(evt.item);
        const onEnd = () => clearHighlights();

        sortableInstances.push(new Sortable(document.getElementById('unassigned-generales'), sharedConfig));
        sortableInstances.push(new Sortable(document.getElementById('unassigned-especialidad'), sharedConfig));
        document.querySelectorAll('.drop-zone').forEach(zone => sortableInstances.push(new Sortable(zone, { ...sharedConfig, onAdd, onStart, onEnd })));
        sortableInstances.push(new Sortable(DOMElements.trash, { ...sharedConfig, onAdd: (evt) => handleDeassign(evt.item) }));
    }

    // --- NUEVA FUNCIÓN: VALIDAR FATIGA DOCENTE ---
    function checkTeacherFatigue(targetCell, courseData) {
        const teacherName = courseData.docente_nombre;
        const day = targetCell.dataset.dia;

        if (!teacherName || teacherName === 'N/A' || !day) return;

        // Buscamos todas las celdas de ESE día en ambas grillas (mañana y tarde)
        // Nota: Esto funciona buscando por el atributo data-dia
        const allCellsOfDay = document.querySelectorAll(`td[data-dia="${day}"]`);

        let consecutiveHours = 0;
        let maxConsecutive = 0;

        // Recorremos las celdas en orden (el DOM las devuelve en orden de aparición: Mañana -> Tarde)
        allCellsOfDay.forEach(cell => {
            // Buscamos si hay un curso asignado en esta celda
            const courseItem = cell.querySelector('.assigned-course-item');
            let isTeacherPresent = false;

            if (courseItem) {
                try {
                    const data = JSON.parse(courseItem.dataset.fullData);
                    // Comparamos nombres (idealmente sería ID, pero nombre funciona visualmente)
                    if (data.docente_nombre === teacherName) {
                        isTeacherPresent = true;
                    }
                } catch (e) { console.error("Error parsing course data for fatigue check"); }
            }

            // Si es la celda donde acabamos de soltar, también cuenta (aunque aún no tenga la clase assigned-course-item renderizada final)
            // Pero como onAdd ocurre cuando el elemento YA está en el DOM de 'to', el querySelector podría encontrarlo o podríamos forzarlo.
            // Para simplificar, asumimos que si cell === targetCell, el docente está presente.
            if (cell === targetCell) {
                isTeacherPresent = true;
            }

            if (isTeacherPresent) {
                consecutiveHours++;
            } else {
                // Si encontramos un hueco, reseteamos el contador, pero guardamos el máximo visto
                if (consecutiveHours > maxConsecutive) maxConsecutive = consecutiveHours;
                consecutiveHours = 0;
            }
        });

        // Chequeo final por si la racha termina al final del día
        if (consecutiveHours > maxConsecutive) maxConsecutive = consecutiveHours;

        // Si detectamos fatiga (ej: > 4 horas seguidas)
        if (maxConsecutive > 4) {
            Toast.fire({
                icon: 'warning',
                title: 'Posible Fatiga Docente',
                text: `El docente ${teacherName} tendría ${maxConsecutive} horas consecutivas este día.`
            });
        }
    }

    async function handleDeassign(courseElement) {
        if (courseElement.classList.contains('static-course')) return;

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
                    if (colorClasses.length) cellToModify.classList.add(...colorClasses);
                }
            }
        }
    }

    function revertVisualSpan(cell) {
        if (!cell) return;
        const duration = parseInt(cell.getAttribute('rowspan') || '1', 10);
        const colorClasses = getCellColorClasses(cell);
        if (colorClasses.length) cell.classList.remove(...colorClasses);
        cell.setAttribute('rowspan', 1);

        if (duration > 1) {
            let currentRow = cell.parentElement;
            for (let i = 1; i < duration; i++) {
                currentRow = currentRow.nextElementSibling;
                if (currentRow) {
                    const cellToShow = currentRow.querySelector(`[data-dia="${cell.dataset.dia}"]`);
                    if (cellToShow) {
                        cellToShow.style.display = '';
                        if (colorClasses.length) cellToShow.classList.remove(...colorClasses);
                    }
                }
            }
        }
    }

    // --- SUGGESTIONS & CONFLICTS VISUALS ---
    // Inject custom styles for suggestions
    const suggestionStyles = document.createElement('style');
    suggestionStyles.innerHTML = `
        .suggestion-cell-best { background-color: rgba(34, 197, 94, 0.2) !important; box-shadow: inset 0 0 0 2px rgba(34, 197, 94, 0.5); }
        .suggestion-cell-good { background-color: rgba(34, 197, 94, 0.1) !important; }
        .conflict-cell { background-color: rgba(239, 68, 68, 0.15) !important; cursor: not-allowed; background-image: repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(239, 68, 68, 0.05) 10px, rgba(239, 68, 68, 0.05) 20px); }
        .conflict-cell-group { background-color: rgba(234, 179, 8, 0.15) !important; cursor: not-allowed; } /* Yellowish for group conflicts? Or just Red/Orange */
        
        @keyframes pulse-green {
            0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
        .suggestion-cell-best { animation: pulse-green 2s infinite; }
    `;
    document.head.appendChild(suggestionStyles);

    async function showSuggestionsAndConflicts(item) {
        clearHighlights();
        const cursoId = item.dataset.cursoId || item.dataset.bloqueId; // Si es bloque moviendo, necesitamos curso_id? No, la API pide curso_id.
        // Si estamos moviendo un bloque ya asignado, item.dataset.fullData tiene el curso_id.

        let realCursoId = item.dataset.cursoId;
        let duracion = item.dataset.duracion;

        if (!realCursoId) {
            try {
                const data = JSON.parse(item.dataset.fullData);
                realCursoId = data.curso_id || data.id; // data.id si viene de la lista no asignados, data.curso_id si es bloque
            } catch (e) { }
        }

        if (!realCursoId) return;

        try {
            const data = await callApi(`/api/get-placement-suggestions/?curso_id=${realCursoId}&duracion=${duracion}`);

            // 1. Highlight Conflicts (Red)
            if (data.conflicts) {
                data.conflicts.forEach(c => {
                    const cell = document.querySelector(`td[data-dia="${c.dia}"][data-franja-id="${c.franja_id}"]`);
                    if (cell) {
                        cell.classList.add('conflict-cell');
                        cell.dataset.conflictReason = c.razon;
                        cell.setAttribute('title', c.razon); // Tooltip nativo

                        // Si es razon de grupo, quizás usar otro color
                        if (c.razon.includes('Grupo')) cell.classList.add('conflict-cell-group');
                    }
                });
            }

            // 2. Highlight Suggestions (Green)
            if (data.suggestions) {
                data.suggestions.forEach(s => {
                    if (s.tipo === 'excelente' || s.is_best) {
                        const cell = document.querySelector(`td[data-dia="${s.dia}"][data-franja-id="${s.franja_id}"]`);
                        if (cell && !cell.classList.contains('conflict-cell')) {
                            cell.classList.add('suggestion-cell-best');
                            cell.setAttribute('title', 'Sugerencia Recomendada');
                        }
                    } else if (s.tipo === 'buena') {
                        const cell = document.querySelector(`td[data-dia="${s.dia}"][data-franja-id="${s.franja_id}"]`);
                        if (cell && !cell.classList.contains('conflict-cell')) {
                            cell.classList.add('suggestion-cell-good');
                        }
                    }
                });
            }

        } catch (error) {
            console.error("Error fetching suggestions:", error);
        }
    }

    function clearHighlights() {
        document.querySelectorAll('.conflict-cell, .suggestion-cell-best, .suggestion-cell-good, .conflict-cell-group').forEach(c => {
            c.classList.remove('conflict-cell', 'suggestion-cell-best', 'suggestion-cell-good', 'conflict-cell-group');
            c.removeAttribute('title');
            delete c.dataset.conflictReason;
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
        const skeletonRow = `<tr><td colspan="${window.PlannerConfig.diasSemana.length + 1}"><div class="skeleton-loader h-48 w-full"></div></td></tr>`;
        DOMElements.gridManana.innerHTML = skeletonRow;
        DOMElements.gridTarde.innerHTML = skeletonRow;
        DOMElements.unassignedContainer.innerHTML = '<div class="skeleton-loader h-16 w-full"></div>';
        try {
            const response = await callApi(`/api/get-cursos-no-asignados/?especialidad_id=${especialidadId}&semestre_cursado=${semestreNum}`);
            if (response.status === 'success') {
                currentPlannerData = response.data;
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
            renderPlanner(data.plannerData);
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
                const diasEspecialidad = await promptSpecialtyDays('global', currentPlannerData?.dias_preferidos_especialidad || []);
                if (!diasEspecialidad) return;

                const btn = DOMElements.globalAutoAssignBtn;
                btn.classList.add('loading', 'btn-disabled');
                Swal.fire({ title: 'Procesando...', text: 'Generando horarios. Por favor, espera.', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
                try {
                    const data = await callApi('/api/generar-horario-automatico/', 'POST', { dias_especialidad: diasEspecialidad });
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

    async function handleGroupAutoAssign() {
        if (!currentPlannerData || !currentPlannerData.grupo_id) {
            return Toast.fire({ icon: 'warning', title: 'Primero selecciona una especialidad.' });
        }

        const groupName = currentPlannerData.grupo_nombre || 'N/A';
        const specialties = currentPlannerData.especialidades_en_grupo || [];
        const specialtiesHtml = specialties.map(s => `<li>${s}</li>`).join('');

        Swal.fire({
            title: `Generar Horario: ${groupName}`,
            html: `
                <div class="text-left mt-4">
                    <p class="mb-2">Se regenerarán los horarios para las siguientes especialidades:</p>
                    <ul class="list-disc ml-6 mb-4 font-semibold text-primary">
                        ${specialtiesHtml}
                    </ul>
                    <p class="text-xs text-base-content/60 bg-base-200 p-2 rounded">
                        <i class="fas fa-info-circle mr-1"></i>
                        Los cursos ya asignados en otros grupos se mantendrán fijos para evitar conflictos.
                    </p>
                </div>
            `,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, generar horario',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#7c3aed', // Purple/Secondary
            width: '32rem'
        }).then(async (result) => {
            if (result.isConfirmed) {
                const diasEspecialidad = await promptSpecialtyDays(groupName, currentPlannerData?.dias_preferidos_especialidad || []);
                if (!diasEspecialidad) return;

                const btn = DOMElements.groupAutoAssignBtn;
                btn.classList.add('loading', 'btn-disabled');
                Swal.fire({ title: 'Procesando...', text: 'Optimizando horario del grupo...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
                try {
                    const data = await callApi('/api/generar-horario-automatico/', 'POST', {
                        grupo_id: currentPlannerData.grupo_id,
                        dias_especialidad: diasEspecialidad
                    });
                    Swal.close();
                    Swal.fire({ title: '¡Grupo Completado!', text: data.message, icon: 'success' });
                    loadPlannerData();
                } catch (error) {
                    Swal.fire({ title: 'Error', text: `Ocurrió un error: ${error.message}`, icon: 'error' });
                } finally {
                    btn.classList.remove('loading', 'btn-disabled');
                }
            }
        });
    }

    async function promptSpecialtyDays(scopeLabel, preselectedDays = []) {
        const checkboxHtml = WEEK_DAYS.map((day) => `
            <label class="flex items-center gap-3 p-3 rounded-lg border border-base-300 hover:border-primary cursor-pointer">
                <input type="checkbox" class="checkbox checkbox-primary specialty-day-checkbox" value="${day}" ${preselectedDays.includes(day) ? 'checked' : ''}>
                <span class="font-medium">${day}</span>
            </label>
        `).join('');

        const result = await Swal.fire({
            title: 'Días para Especialidad',
            html: `
                <div class="text-left space-y-3">
                    <p class="text-sm">
                        Elige exactamente <strong>2 días</strong> en los que se programarán los cursos de especialidad para <strong>${scopeLabel}</strong>.
                    </p>
                    <div class="grid grid-cols-1 gap-2 mt-3">
                        ${checkboxHtml}
                    </div>
                    <p class="text-xs text-base-content/60">
                        Ejemplo: Lunes y Viernes, o Martes y Jueves.
                    </p>
                </div>
            `,
            width: '34rem',
            showCancelButton: true,
            confirmButtonText: 'Usar estos días',
            cancelButtonText: 'Cancelar',
            focusConfirm: false,
            preConfirm: () => {
                const selected = Array.from(document.querySelectorAll('.specialty-day-checkbox:checked'))
                    .map((input) => input.value);

                if (selected.length !== 2) {
                    Swal.showValidationMessage('Selecciona exactamente 2 días.');
                    return false;
                }

                return selected;
            }
        });

        return result.isConfirmed ? result.value : null;
    }

    if (DOMElements.toggleGeneralEdit) {
        DOMElements.toggleGeneralEdit.addEventListener('change', () => {
            if (currentPlannerData) {
                renderPlanner(currentPlannerData);
                const msg = DOMElements.toggleGeneralEdit.checked ? 'Edición de Generales HABILITADA' : 'Edición de Generales BLOQUEADA';
                const icon = DOMElements.toggleGeneralEdit.checked ? 'success' : 'info';
                Toast.fire({ icon: icon, title: msg });
            }
        });
    }

    if (DOMElements.especialidad) DOMElements.especialidad.addEventListener('change', loadPlannerData);
    if (DOMElements.semestre) DOMElements.semestre.addEventListener('change', loadPlannerData);
    if (DOMElements.autoAssignBtn) DOMElements.autoAssignBtn.addEventListener('click', handleAutoAssign);
    if (DOMElements.groupAutoAssignBtn) DOMElements.groupAutoAssignBtn.addEventListener('click', handleGroupAutoAssign);
    if (DOMElements.globalAutoAssignBtn) DOMElements.globalAutoAssignBtn.addEventListener('click', handleGlobalAutoAssign);
    if (DOMElements.clearScheduleBtn) DOMElements.clearScheduleBtn.addEventListener('click', handleClearSchedule);

    async function handleClearSchedule() {
        if (!currentPlannerData || !currentPlannerData.grupo_id) {
            return Toast.fire({ icon: 'warning', title: 'Primero selecciona una especialidad.' });
        }

        const { value: clearType } = await Swal.fire({
            title: '¿Qué deseas limpiar?',
            icon: 'warning',
            input: 'select',
            inputOptions: {
                'especialidad': 'Solo la vista actual (Especialidad/Semestre)',
                'grupo': `Todo el Grupo (${currentPlannerData.grupo_nombre})`,
                'global': 'TODO el Semestre (Global)'
            },
            inputPlaceholder: 'Selecciona una opción',
            showCancelButton: true,
            confirmButtonText: 'Confirmar Limpieza',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#d33',
            inputValidator: (value) => {
                if (!value) return 'Debes seleccionar una opción';
            }
        });

        if (clearType) {
            const body = { tipo: clearType };
            if (clearType === 'grupo') body.grupo_id = currentPlannerData.grupo_id;
            if (clearType === 'especialidad') {
                body.especialidad_id = DOMElements.especialidad.value;
                body.semestre_cursado = DOMElements.semestre.value;
            }

            Swal.fire({ title: 'Limpiando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

            try {
                const data = await callApi('/api/clear-horario/', 'POST', body);
                Swal.fire({ title: '¡Limpieza Exitosa!', text: data.message, icon: 'success' });
                loadPlannerData();
            } catch (error) {
                Swal.fire({ title: 'Error', text: error.message, icon: 'error' });
            }
        }
    }

    if (DOMElements.searchInput) {
        DOMElements.searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            document.querySelectorAll('#unassigned-courses-container > .collapse .p-2.rounded-lg').forEach(card => {
                // Buscamos dentro del texto visible de la tarjeta
                card.style.display = card.innerText.toLowerCase().includes(searchTerm) ? '' : 'none';
            });
        });
    }

    const sidebarTabs = document.querySelectorAll('.planner-sidebar .tabs .tab');
    sidebarTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            sidebarTabs.forEach(t => t.classList.remove('tab-active'));
            tab.classList.add('tab-active');
            document.querySelectorAll('#tab-manual, #tab-auto').forEach(c => c.classList.remove('active'));
            document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
        });
    });

    if (DOMElements.scheduleTabsContainer) {
        DOMElements.scheduleTabsContainer.addEventListener('click', (e) => {
            if (e.target.matches('.tab')) {
                e.preventDefault();
                DOMElements.scheduleTabsContainer.querySelectorAll('.tab').forEach(tab => tab.classList.remove('tab-active'));
                e.target.classList.add('tab-active');
                document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
                const targetPane = document.querySelector(e.target.dataset.tabTarget);
                if (targetPane) targetPane.classList.add('active');
            }
        });
    }

    if (DOMElements.especialidad && DOMElements.especialidad.value && DOMElements.semestre && DOMElements.semestre.value) {
        loadPlannerData();
    }
});
