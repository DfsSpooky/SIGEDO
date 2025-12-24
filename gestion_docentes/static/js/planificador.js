/**
 * planificador.js - Versión PRO Corregida (Stable)
 * Soluciona el error de desaparición de pestañas y contenedores.
 */

document.addEventListener('DOMContentLoaded', function () {
    if (window.plannerConfig) initPlanner(window.plannerConfig);
});

function initPlanner(config) {
    const { urls, franjasManana, franjasTarde, diasSemana, csrfToken } = config;
    
    // Selectores DOM
    const els = {
        esp: document.querySelector('#especialidad'),
        sem: document.querySelector('#semestre_cursado'),
        body: document.querySelector('#planner-body'),
        placeholder: document.querySelector('#planner-placeholder'),
        gridM: document.querySelector('#schedule-grid-manana'),
        gridT: document.querySelector('#schedule-grid-tarde'),
        sidebar: document.querySelector('#unassigned-courses-container'),
        trash: document.querySelector('#trash-zone'),
        autoBtn: document.querySelector('#auto-assign-btn'),
        search: document.querySelector('#course-search-input'),
        // Contenedores principales de los turnos (Para togglear visibilidad)
        containerM: document.querySelector('#container-manana'),
        containerT: document.querySelector('#container-tarde')
    };
    
    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 2000 });
    let sortables = [];

    // --- 1. RENDERIZADO DE TARJETAS (Glassmorphism) ---
    function createCard(curso, isAssigned) {
        const div = document.createElement('div');
        
        // A. BLOQUES DE GESTIÓN (Gris, Estático)
        if (curso.es_gestion) {
            div.className = "course-card card-gestion h-full flex flex-col justify-center p-1 rounded select-none shadow-sm";
            div.innerHTML = `
                <div class="flex items-center justify-center text-slate-400 mb-0.5">
                    <i class="fas fa-coffee text-[10px] mr-1"></i>
                    <span class="text-[8px] font-bold uppercase tracking-widest">Gestión</span>
                </div>
                <div class="text-[10px] font-semibold text-slate-500 text-center leading-tight truncate px-1">${curso.nombre}</div>
            `;
            return div;
        }

        // B. CURSOS ACADÉMICOS
        const typeClass = curso.tipo_curso === 'GENERAL' ? 'card-general' : 'card-especialidad';
        
        if (isAssigned) {
            div.className = `course-card ${typeClass} relative h-full flex flex-col p-1.5 rounded-md cursor-grab active:cursor-grabbing group shadow-sm`;
            div.dataset.bloqueId = curso.bloque_id;
            div.dataset.cursoId = curso.curso_id;
        } else {
            div.className = `course-card ${typeClass} p-2 mb-2 rounded-md shadow-sm cursor-grab border-l-4 hover:shadow-md transition-shadow`;
            div.dataset.cursoId = curso.id;
            div.dataset.duracion = Math.min(2, curso.horas_pendientes);
        }

        const icon = curso.tipo_curso === 'GENERAL' ? 'fa-globe' : 'fa-book';
        const teacherName = curso.docente_nombre || "Sin Docente";
        
        // Tooltip
        const tooltipHTML = `
            <div class="course-tooltip text-left">
                <div class="font-bold text-white mb-1 border-b border-gray-600 pb-1 truncate">${curso.nombre}</div>
                <div class="mb-0.5"><i class="fas fa-user-tie mr-1 text-gray-400"></i> ${teacherName}</div>
                ${isAssigned ? `<div><i class="far fa-clock mr-1 text-gray-400"></i> ${curso.duracion_bloques} bloques</div>` : ''}
                <div class="mt-1 text-[9px] text-gray-400 uppercase tracking-wide flex justify-between">
                    <span>${curso.tipo_curso}</span>
                    ${curso.excepcion_horario ? '<span class="text-amber-400"><i class="fas fa-exclamation-triangle"></i> Horario Esp.</span>' : ''}
                </div>
            </div>
        `;

        div.innerHTML = `
            ${tooltipHTML}
            <div class="font-bold text-[11px] text-slate-800 leading-tight mb-0.5 truncate pr-4">${curso.nombre}</div>
            <div class="text-[10px] text-slate-500 truncate mb-auto flex items-center">
                <i class="fas fa-user text-[8px] mr-1 opacity-50"></i>${teacherName}
            </div>
            
            ${isAssigned ? `
                <div class="flex justify-between items-end border-t border-black/5 pt-1 mt-1">
                    <span class="text-[9px] font-mono text-slate-500 font-medium bg-white/50 px-1 rounded shadow-sm">${curso.duracion_bloques}h</span>
                    <i class="fas ${icon} text-[10px] text-slate-400"></i>
                </div>
                <div class="absolute top-1 right-1 flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                    <button onmousedown="event.stopPropagation()" onclick="deleteBloque(this)" class="w-4 h-4 flex items-center justify-center rounded-full text-[8px] text-white bg-red-400 hover:bg-red-500 shadow-sm transition-transform hover:scale-110" title="Eliminar"><i class="fas fa-times"></i></button>
                    <div class="flex gap-1">
                         <button onmousedown="event.stopPropagation()" onclick="changeDuration('${curso.bloque_id}', 'decrease')" class="w-4 h-4 flex items-center justify-center rounded-full text-[8px] text-white bg-amber-400 hover:bg-amber-500 shadow-sm transition-transform hover:scale-110">-</button>
                         <button onmousedown="event.stopPropagation()" onclick="changeDuration('${curso.bloque_id}', 'increase')" class="w-4 h-4 flex items-center justify-center rounded-full text-[8px] text-white bg-emerald-400 hover:bg-emerald-500 shadow-sm transition-transform hover:scale-110">+</button>
                    </div>
                </div>
            ` : `
                <div class="mt-2 flex items-center justify-between">
                    <span class="text-[9px] px-2 py-0.5 rounded-full bg-white/60 text-slate-600 font-bold border border-slate-200">${curso.horas_pendientes}h pendientes</span>
                    <i class="fas fa-grip-lines text-slate-300"></i>
                </div>
            `}
        `;
        return div;
    }

    // --- 2. RENDERIZADO DEL GRID ---
    function render(data) {
        // Limpiar grids
        [els.gridM, els.gridT].forEach((grid, idx) => {
            grid.innerHTML = '';
            const franjas = idx === 0 ? franjasManana : franjasTarde;
            franjas.forEach(f => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="text-center p-0 align-middle border-b border-r border-slate-100 bg-slate-50/30">
                        <div class="text-[10px] font-bold text-slate-500">${f.hora_inicio.slice(0,5)}</div>
                        <div class="text-[9px] text-slate-400">${f.hora_fin.slice(0,5)}</div>
                    </td>`;
                diasSemana.forEach(dia => {
                    tr.innerHTML += `<td class="p-1 border-b border-r border-slate-100 align-top relative drop-zone transition-colors h-16" data-dia="${dia}" data-franja-id="${f.id}"></td>`;
                });
                grid.appendChild(tr);
            });
        });

        // Llenar Sidebar
        els.sidebar.innerHTML = '';
        const addSection = (title, items) => {
            if(!items.length) return;
            const header = document.createElement('div');
            header.className = "text-[10px] font-bold uppercase text-slate-400 mt-4 mb-2 pl-1 tracking-wider";
            header.textContent = title;
            els.sidebar.appendChild(header);
            items.forEach(c => els.sidebar.appendChild(createCard(c, false)));
        };
        addSection('Cursos de Especialidad', data.cursos_pendientes.especialidad);
        addSection('Cursos Generales', data.cursos_pendientes.generales);

        if (data.cursos_pendientes.especialidad.length === 0 && data.cursos_pendientes.generales.length === 0) {
             els.sidebar.innerHTML = '<div class="text-center p-8 text-xs text-slate-400 italic">🎉 ¡Todo asignado!</div>';
        }

        // Llenar Cursos Asignados
        data.cursos_asignados.forEach(c => {
            const cell = document.querySelector(`td[data-dia="${c.dia}"][data-franja-id="${c.franja_id_inicio}"]`);
            if(cell) {
                const card = createCard(c, true);
                cell.appendChild(card);
                if(c.duracion_bloques > 1) applyRowspan(cell, c.duracion_bloques);
            }
        });

        initDrag();
    }

    // --- 3. DRAG & DROP ---
    function initDrag() {
        sortables.forEach(s => s.destroy());
        sortables = [];
        
        const config = {
            group: 'shared', 
            animation: 150, 
            ghostClass: 'opacity-40',
            filter: (evt) => !evt.target.closest('[data-curso-id]'), 
            
            onStart: (evt) => {
                document.body.classList.add('grabbing');
                const cursoId = evt.item.dataset.cursoId;
                if (cursoId) highlightConflicts(cursoId);
            },
            onEnd: () => {
                document.body.classList.remove('grabbing');
                document.querySelectorAll('.conflict-zone').forEach(c => {
                    c.classList.remove('conflict-zone');
                    c.removeAttribute('title');
                });
            }
        };

        document.querySelectorAll('.drop-zone').forEach(el => {
            sortables.push(new Sortable(el, {
                ...config,
                onAdd: async (evt) => {
                    const item = evt.item;
                    const to = evt.to;
                    const from = evt.from;
                    if(from.tagName === 'TD') revertRowspan(from);

                    if(to.children.length > 1) {
                        Toast.fire({icon:'warning', title:'Espacio ocupado'});
                        return loadData();
                    }

                    try {
                        const payload = item.dataset.bloqueId 
                            ? { bloque_id: item.dataset.bloqueId, dia: to.dataset.dia, franja_id: to.dataset.franjaId }
                            : { curso_id: item.dataset.cursoId, dia: to.dataset.dia, franja_id: to.dataset.franjaId, duracion: item.dataset.duracion };
                        
                        const url = item.dataset.bloqueId ? urls.move : urls.assign;
                        await api(url, payload);
                        loadData();
                    } catch(e) {
                        Toast.fire({icon:'error', title: e.message});
                        loadData();
                    }
                }
            }));
        });

        sortables.push(new Sortable(els.sidebar, { ...config, sort: false }));
        sortables.push(new Sortable(els.trash, { 
            ...config, 
            onAdd: async (evt) => {
                const item = evt.item;
                if(!item.dataset.bloqueId) { item.remove(); return; }
                try {
                    await api(urls.deassign, { bloque_id: item.dataset.bloqueId });
                    loadData();
                } catch(e) { 
                    Toast.fire({icon:'error', title: e.message});
                    loadData(); 
                }
            }
        }));
    }

    async function highlightConflicts(cursoId) {
        try {
            const res = await fetch(`${urls.conflicts}?curso_id=${cursoId}`, { headers: {'X-CSRFToken': csrfToken} });
            const data = await res.json();
            if(data.data?.conflicts) {
                data.data.conflicts.forEach(c => {
                    const cell = document.querySelector(`td[data-dia="${c.dia}"][data-franja-id="${c.franja_id}"]`);
                    if(cell) {
                        cell.classList.add('conflict-zone');
                        cell.title = `⛔ No disponible: ${c.razon}`;
                    }
                });
            }
        } catch(e) { console.error(e); }
    }

    // --- UTILIDADES ---
    window.changeDuration = async (id, action) => {
        event.stopPropagation();
        try { await api(urls.duration, { bloque_id: id, accion: action }); loadData(); } catch(e){ Toast.fire({icon:'error', title: e.message}); }
    };
    window.deleteBloque = async (btn) => {
        event.stopPropagation();
        const card = btn.closest('[data-bloque-id]');
        try { await api(urls.deassign, { bloque_id: card.dataset.bloqueId }); loadData(); } catch(e){ Toast.fire({icon:'error', title: e.message}); }
    };

    async function api(url, data) {
        const res = await fetch(url, {
            method: 'POST', 
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
            body: JSON.stringify(data)
        });
        const json = await res.json();
        if(!res.ok) throw new Error(json.message || 'Error del servidor');
        return json;
    }

    async function loadData() {
        if(!els.esp.value || !els.sem.value) {
            els.body.classList.add('hidden');
            els.placeholder.classList.remove('hidden');
            return;
        }
        
        els.placeholder.classList.add('hidden');
        els.body.classList.remove('hidden');

        try {
            const res = await fetch(`${urls.getData}?especialidad_id=${els.esp.value}&semestre_cursado=${els.sem.value}`, { headers: {'X-CSRFToken': csrfToken} });
            const json = await res.json();
            render(json.data);
        } catch(e) { console.error(e); }
    }
    
    function applyRowspan(cell, span) {
        cell.rowSpan = span;
        let next = cell.parentElement.nextElementSibling;
        for(let i=1; i<span && next; i++) {
            const target = next.querySelector(`td[data-dia="${cell.dataset.dia}"]`);
            if(target) target.style.display = 'none';
            next = next.nextElementSibling;
        }
    }
    
    function revertRowspan(cell) {
        const span = parseInt(cell.rowSpan || 1);
        cell.rowSpan = 1;
        let next = cell.parentElement.nextElementSibling;
        for(let i=1; i<span && next; i++) {
            const target = next.querySelector(`td[data-dia="${cell.dataset.dia}"]`);
            if(target) target.style.display = '';
            next = next.nextElementSibling;
        }
    }

    // --- LISTENERS ---
    els.esp.addEventListener('change', loadData);
    els.sem.addEventListener('change', loadData);
    
    els.search.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        document.querySelectorAll('.course-card').forEach(card => {
            if(!card.closest('td')) {
                const txt = card.textContent.toLowerCase();
                card.style.display = txt.includes(term) ? '' : 'none';
            }
        });
    });

    els.autoBtn.addEventListener('click', async () => {
        els.autoBtn.disabled = true;
        els.autoBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Asignando...';
        try { await api(urls.autoAssign, {especialidad_id: els.esp.value, semestre_cursado: els.sem.value}); loadData(); }
        catch(e) { Toast.fire({icon:'error', title: e.message}); }
        finally { els.autoBtn.disabled = false; els.autoBtn.innerHTML = '<i class="fas fa-magic"></i> Auto-Asignar'; }
    });
    
    // --- LÓGICA DE TABS CORREGIDA ---
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // 1. Resetear estilos de todos los botones
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('text-blue-600', 'border-b-2', 'border-blue-600', 'bg-white');
                b.classList.add('text-slate-400');
            });
            // 2. Activar estilo del botón clickeado
            btn.classList.add('text-blue-600', 'border-b-2', 'border-blue-600', 'bg-white');
            btn.classList.remove('text-slate-400');
            
            // 3. Ocultar AMBOS contenedores explícitamente (SOLUCIÓN AL BUG)
            els.containerM.classList.add('hidden');
            els.containerT.classList.add('hidden');

            // 4. Mostrar solo el objetivo
            const targetId = btn.dataset.target; // ej: #container-tarde
            document.querySelector(targetId).classList.remove('hidden');
        });
    });

    if(els.esp.value && els.sem.value) loadData();
}