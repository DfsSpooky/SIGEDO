from ortools.sat.python import cp_model
from core.models.academic import Curso, Semestre
from core.models.scheduling import BloqueHorario, FranjaHoraria, Aula, BloqueNoLectivo
from django.db import transaction

class HorarioSolver:
    def __init__(self, semestre_nombre="2026-A"):
        self.semestre_nombre = semestre_nombre
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.assignments = {}  # (curso_id, dia, franja_id) -> bool var
        self.data = self._load_data()

    def _load_data(self):
        semestre = Semestre.objects.get(nombre=self.semestre_nombre)
        cursos = list(Curso.objects.filter(semestre=semestre).select_related('docente'))
        franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        aulas = list(Aula.objects.all())
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        # Bloques no lectivos por docente
        no_lectivos = {}
        for bnl in BloqueNoLectivo.objects.all():
            if bnl.docente_id not in no_lectivos:
                no_lectivos[bnl.docente_id] = []
            no_lectivos[bnl.docente_id].append((bnl.dia, bnl.franja_inicio_id, bnl.duracion_bloques))

        return {
            'cursos': cursos,
            'franjas': franjas,
            'aulas': aulas,
            'dias': dias,
            'no_lectivos': no_lectivos
        }

    def solve(self, fixed_assignments=None):
        """
        fixed_assignments: list of (curso_id, dia, franja_id) that MUST be respected (for chatbot).
        """
        cursos = self.data['cursos']
        franjas = self.data['franjas']
        aulas = self.data['aulas']
        dias = self.data['dias']
        
        # Variables: x[c, d, f, a] is true if curso c is scheduled at day d, slot f, in aula a
        x = {}
        for c in cursos:
            for d in dias:
                for f in franjas:
                    for a in aulas:
                        x[c.id, d, f.id, a.id] = self.model.NewBoolVar(f'x_{c.id}_{d}_{f.id}_{a.id}')

        # Constraint 1: Un curso debe cumplir sus horas semanales
        for c in cursos:
            required_slots = c.horas_academicas_semanales
            self.model.Add(sum(x[c.id, d, f.id, a.id] for d in dias for f in franjas for a in aulas) == required_slots)

        # Constraint 2: Un docente no puede dictar dos cursos al mismo tiempo
        docentes_ids = set(c.docente_id for c in cursos if c.docente_id)
        for d_id in docentes_ids:
            cursos_docente = [c for c in cursos if c.docente_id == d_id]
            for d in dias:
                for f in franjas:
                    self.model.Add(sum(x[c.id, d, f.id, a.id] for c in cursos_docente for a in aulas) <= 1)

        # Constraint 3: Un aula no puede tener dos clases simultáneas
        for a in aulas:
            for d in dias:
                for f in franjas:
                    self.model.Add(sum(x[c.id, d, f.id, a.id] for c in cursos) <= 1)

        # Constraint 4: Turnos obligatorios por semestre
        # Semestres 1-4: Mañana (08:00 - 13:00)
        # Semestres 5-10: Tarde (14:00 - 20:40)
        for c in cursos:
            if c.semestre_cursado:
                for d in dias:
                    for f in franjas:
                        for a in aulas:
                            if c.semestre_cursado <= 4 and f.turno != "MANANA" and not c.excepcion_horario:
                                self.model.Add(x[c.id, d, f.id, a.id] == 0)
                            elif c.semestre_cursado >= 5 and f.turno == "MANANA":
                                self.model.Add(x[c.id, d, f.id, a.id] == 0)

        # Constraint 5: Límite diario del docente (max 8 horas)
        for d_id in docentes_ids:
            cursos_docente = [c for c in cursos if c.docente_id == d_id]
            for d in dias:
                self.model.Add(sum(x[c.id, d, f.id, a.id] for c in cursos_docente for f in franjas for a in aulas) <= 8)

        # Constraint 6: Carga continua (max 4 horas sin descanso) - Soft/Hard combination
        # For simplicity, we enforce that in any window of 5 slots, a teacher has at most 4 slots.
        for d_id in docentes_ids:
            cursos_docente = [c for c in cursos if c.docente_id == d_id]
            for d in dias:
                for i in range(len(franjas) - 4):
                    window = franjas[i:i+5]
                    self.model.Add(sum(x[c.id, d, f.id, a.id] for c in cursos_docente for f in window for a in aulas) <= 4)

        # Constraint 7: Horas Administrativas (Respect BloqueNoLectivo)
        for c in cursos:
            if c.docente_id in self.data['no_lectivos']:
                for (dia_bnl, f_start_id, duration) in self.data['no_lectivos'][c.docente_id]:
                    # Find all franjas that overlap with this BNL
                    try:
                        f_start_idx = next(i for i, f in enumerate(franjas) if f.id == f_start_id)
                        f_overlap_ids = [franjas[j].id for j in range(f_start_idx, min(f_start_idx + duration, len(franjas)))]
                        for f_id in f_overlap_ids:
                            for a in aulas:
                                self.model.Add(x[c.id, dia_bnl, f_id, a.id] == 0)
                    except StopIteration:
                        continue

        # Add fixed assignments (for chatbot reprogramming)
        if fixed_assignments:
            for c_id, dia, f_id in fixed_assignments:
                # We need to make sure this assignment exists in SOMETIME aula
                self.model.Add(sum(x[c_id, dia, f_id, a.id] for a in aulas) == 1)

        # Soft Constraint: Contiguity (try to keep course slots together on the same day)
        # This is more complex, but we can add a small objective to prefer assignments 
        # that are adjacent to others of the same course.
        # For now, let's just Solve to find ANY feasible solution.

        status = self.solver.Solve(self.model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            results = []
            for c in cursos:
                for d in dias:
                    for f in franjas:
                        for a in aulas:
                            if self.solver.Value(x[c.id, d, f.id, a.id]) == 1:
                                results.append({
                                    'curso': c,
                                    'dia': d,
                                    'franja': f,
                                    'aula': a
                                })
            return results
        else:
            return None

    @transaction.atomic
    def save_results(self, results):
        if not results:
            return False
            
        semestre = Semestre.objects.get(nombre=self.semestre_nombre)
        # Delete old blocks for this semester
        BloqueHorario.objects.filter(curso__semestre=semestre).delete()
        
        # Sort results to facilitate merging
        # Sort by course, day, aula, and then by slot start time (franja.id or hora_inicio)
        results.sort(key=lambda r: (r['curso'].id, r['dia'], r['aula'].id, r['franja'].hora_inicio))

        merged_blocks = []
        if results:
            current_block = {
                'curso': results[0]['curso'],
                'dia': results[0]['dia'],
                'franja_inicio': results[0]['franja'],
                'aula': results[0]['aula'],
                'duracion': 1
            }
            
            franjas_list = list(FranjaHoraria.objects.order_by('hora_inicio'))
            franja_to_idx = {f.id: i for i, f in enumerate(franjas_list)}

            for i in range(1, len(results)):
                r = results[i]
                prev_idx = franja_to_idx[results[i-1]['franja'].id]
                curr_idx = franja_to_idx[r['franja'].id]
                
                # Check if it's the same course, day, aula and the slot is contiguous
                if (r['curso'].id == current_block['curso'].id and 
                    r['dia'] == current_block['dia'] and 
                    r['aula'].id == current_block['aula'].id and
                    curr_idx == prev_idx + 1):
                    current_block['duracion'] += 1
                else:
                    merged_blocks.append(current_block)
                    current_block = {
                        'curso': r['curso'],
                        'dia': r['dia'],
                        'franja_inicio': r['franja'],
                        'aula': r['aula'],
                        'duracion': 1
                    }
            merged_blocks.append(current_block)

        # Save merged blocks
        for mb in merged_blocks:
            BloqueHorario.objects.create(
                curso=mb['curso'],
                dia=mb['dia'],
                franja_inicio=mb['franja_inicio'],
                aula=mb['aula'],
                duracion_bloques=mb['duracion']
            )
        return True
