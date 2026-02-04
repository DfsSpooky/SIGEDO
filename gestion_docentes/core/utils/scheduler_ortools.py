
import collections
from ortools.sat.python import cp_model
from django.db.models import Q
from core.models import Curso, BloqueHorario, FranjaHoraria, Especialidad, Docente, Grupo

class TimetableSolver:
    def __init__(self, semestre, grupo_id=None):
        self.semestre = semestre
        self.grupo_id = grupo_id
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = 30.0  # Limit to 30s
        
        # Cursos a asignar ahora (en el scope actual)
        q_scope = Q(semestre=semestre, docente__isnull=False)
        if grupo_id:
            q_scope &= Q(especialidades__grupo_id=grupo_id)
            
        self.cursos = list(Curso.objects.filter(q_scope).prefetch_related('especialidades').distinct())
        
        # Bloques ya existentes de OTROS grupos/cursos que NO vamos a resetear
        # Estos se tratarán como restricciones fijas
        q_externos = Q(curso__semestre=semestre)
        if grupo_id:
            # Excluir los bloques que pertenecen al grupo que estamos reseteando
            q_externos &= ~Q(curso__especialidades__grupo_id=grupo_id)
        else:
            # Si es global, no hay externos (todo se resetea)
            q_externos = Q(id__lt=0) # Query vacía
            
        self.bloques_externos = list(BloqueHorario.objects.filter(q_externos).select_related('curso__docente').prefetch_related('curso__especialidades'))
        
        self.franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        self.dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        self.franja_map = {f.id: i for i, f in enumerate(self.franjas)}
        
        # Variables: x[c, d, s] -> Course c assigned to Day d at Slot s
        self.x = {}
        for c in self.cursos:
            for d in self.dias:
                for s_idx in range(len(self.franjas)):
                    self.x[(c.id, d, s_idx)] = self.model.NewBoolVar(f'x_{c.id}_{d}_{s_idx}')

    def solve(self):
        self._add_hard_constraints()
        self._set_objective()
        
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return self._save_results()
        else:
            return False, "No se pudo encontrar una solución factible con las restricciones dadas."

    def _add_hard_constraints(self):
        # --- Pre-procesar Ocupación Externa (Bloques que no estamos moviendo) ---
        extern_docente_ocupado = collections.defaultdict(set) # {docente_id: {(dia, s_idx)}}
        extern_grupo_ocupado = collections.defaultdict(set)   # {(grupo_id, semestre, esp_id): {(dia, s_idx)}}
        
        for b in self.bloques_externos:
            try:
                s_start = self.franja_map[b.franja_inicio_id]
                for i in range(b.duracion_bloques):
                    slot = s_start + i
                    if b.curso.docente_id:
                        extern_docente_ocupado[b.curso.docente_id].add((b.dia, slot))
                    for esp in b.curso.especialidades.all():
                        extern_grupo_ocupado[(esp.grupo_id, b.curso.semestre_cursado, esp.id)].add((b.dia, slot))
            except KeyError: continue

        # 1. Weekly Hours Requirement
        for c in self.cursos:
            self.model.Add(sum(self.x[(c.id, d, s)] for d in self.dias for s in range(len(self.franjas))) == c.horas_academicas_semanales)

        # 2. Teacher Overlap & Capacity
        docentes = set(c.docente for c in self.cursos if c.docente)
        for d in self.dias:
            for s in range(len(self.franjas)):
                for doc in docentes:
                    # Si el docente ya está ocupado externamente en este slot, forzamos x = 0 para todos sus cursos en el scope
                    if (d, s) in extern_docente_ocupado[doc.id]:
                        for c in self.cursos:
                            if c.docente_id == doc.id:
                                self.model.Add(self.x[(c.id, d, s)] == 0)
                    else:
                        c_ids = [c.id for c in self.cursos if c.docente_id == doc.id]
                        self.model.Add(sum(self.x[(c_id, d, s)] for c_id in c_ids) <= 1)

        # 3. Student Group Overlap
        for d in self.dias:
            for s in range(len(self.franjas)):
                # Each Specialty at each Semester can only have 1 class
                especialidades = Especialidad.objects.all()
                for esp in especialidades:
                    for sem in range(1, 11):
                        # Cursos en el scope actual para esta especialidad/semestre
                        c_ids_at_sem = [c.id for c in self.cursos if esp in c.especialidades.all() and c.semestre_cursado == sem]
                        
                        # Si esta especialidad/semestre ya tiene un bloque externo en este slot
                        if (d, s) in extern_grupo_ocupado[(esp.grupo_id, sem, esp.id)]:
                            for cid in c_ids_at_sem:
                                self.model.Add(self.x[(cid, d, s)] == 0)
                        elif c_ids_at_sem:
                            self.model.Add(sum(self.x[(cid, d, s)] for cid in c_ids_at_sem) <= 1)

        # 4. Turn & Teacher Availability
        for c in self.cursos:
            doc = c.docente
            for d in self.dias:
                for s_idx, f in enumerate(self.franjas):
                    valid = True
                    if doc.disponibilidad == "MANANA" and f.turno != "MANANA": valid = False
                    if doc.disponibilidad == "TARDE" and f.turno != "TARDE": valid = False
                    if c.semestre_cursado:
                        if c.semestre_cursado <= 4:
                            if f.turno == "TARDE" and not c.excepcion_horario: valid = False
                        else: # >= 5
                            if f.turno == "MANANA": valid = False
                    if not valid:
                        self.model.Add(self.x[(c.id, d, s_idx)] == 0)

        # 5. Daily Limits
        for d in self.dias:
            for doc in docentes:
                c_ids = [c.id for c in self.cursos if c.docente_id == doc.id]
                # Horas externas ya asignadas a este docente este día
                h_externas = sum(1 for (dia, slot) in extern_docente_ocupado[doc.id] if dia == d)
                self.model.Add(sum(self.x[(cid, d, s)] for cid in c_ids for s in range(len(self.franjas))) <= (8 - h_externas))
            
            for esp in Especialidad.objects.all():
                for sem in range(1, 11):
                    c_ids = [c.id for c in self.cursos if esp in c.especialidades.all() and c.semestre_cursado == sem]
                    if c_ids:
                        h_externas = sum(1 for (dia, slot) in extern_grupo_ocupado[(esp.grupo_id, sem, esp.id)] if dia == d)
                        self.model.Add(sum(self.x[(cid, d, s)] for cid in c_ids for s in range(len(self.franjas))) <= (6 - h_externas))

        # 6. Minimum session length (at least 2 consecutive slots)
        # This prevents isolated 1-hour blocks
        for c in self.cursos:
            if c.horas_academicas_semanales >= 2:
                for d in self.dias:
                    num_slots = len(self.franjas)
                    for s in range(num_slots):
                        if s == 0:
                            self.model.Add(self.x[(c.id, d, 0)] <= self.x[(c.id, d, 1)])
                        elif s == num_slots - 1:
                            self.model.Add(self.x[(c.id, d, s)] <= self.x[(c.id, d, s-1)])
                        else:
                            # x[s] == 1 => x[s-1] == 1 OR x[s+1] == 1
                            self.model.Add(self.x[(c.id, d, s)] <= self.x[(c.id, d, s-1)] + self.x[(c.id, d, s+1)])

    def _set_objective(self):
        # Goal: Group General and Specialty courses on specific days
        groups = set()
        for c in self.cursos:
            for esp in c.especialidades.all():
                if esp.grupo: groups.add(esp.grupo)
        
        penalties = []
        for g in groups:
            for sem in range(1, 11):
                courses_g = [c for c in self.cursos if c.semestre_cursado == sem and g in [e.grupo for e in c.especialidades.all() if e.grupo]]
                if not courses_g: continue
                
                generales = [c for c in courses_g if c.tipo_curso == 'GENERAL']
                especialidades = [c for c in courses_g if c.tipo_curso == 'ESPECIALIDAD']
                
                for d in self.dias:
                    if generales:
                        var = self.model.NewBoolVar(f'day_gen_{g.id}_{sem}_{d}')
                        self.model.Add(sum(self.x[(c.id, d, s)] for c in generales for s in range(len(self.franjas))) <= len(self.franjas) * var)
                        penalties.append(var * 10)
                    
                    if especialidades:
                        var = self.model.NewBoolVar(f'day_esp_{g.id}_{sem}_{d}')
                        self.model.Add(sum(self.x[(c.id, d, s)] for c in especialidades for s in range(len(self.franjas))) <= len(self.franjas) * var)
                        penalties.append(var * 5)
        
        self.model.Minimize(sum(penalties))

    def _save_results(self):
        # Reset current schedule ONLY for the courses in scope
        curso_ids = [c.id for c in self.cursos]
        BloqueHorario.objects.filter(curso_id__in=curso_ids).delete()
        
        bloques_creados = 0
        for d in self.dias:
            for c in self.cursos:
                # Group consecutive slots into one BloqueHorario
                current_start = None
                duration = 0
                
                for s_idx in range(len(self.franjas)):
                    if self.solver.Value(self.x[(c.id, d, s_idx)]) == 1:
                        if current_start is None:
                            current_start = self.franjas[s_idx]
                            duration = 1
                        else:
                            duration += 1
                    else:
                        if current_start:
                            # Save block
                            BloqueHorario.objects.create(
                                curso=c,
                                dia=d,
                                franja_inicio=current_start,
                                duracion_bloques=duration
                            )
                            bloques_creados += 1
                            current_start = None
                            duration = 0
                # Final block if any
                if current_start:
                    BloqueHorario.objects.create(
                        curso=c,
                        dia=d,
                        franja_inicio=current_start,
                        duracion_bloques=duration
                    )
                    bloques_creados += 1
        
        return True, f"Asignación automática exitosa. Se crearon {bloques_creados} bloques horarios."
