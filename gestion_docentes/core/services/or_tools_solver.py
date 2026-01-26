from ortools.sat.python import cp_model
from core.models.academic import Curso, Semestre
from core.models.scheduling import BloqueHorario, FranjaHoraria, Aula, BloqueNoLectivo
from django.db import transaction
from django.db.models import Prefetch

class HorarioSolver:
    def __init__(self, semestre_nombre="2026-A"):
        self.semestre_nombre = semestre_nombre
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        # Enable multiple workers for performance if available
        self.solver.parameters.num_search_workers = 8
        self.data = self._load_data()

    def _load_data(self):
        semestre = Semestre.objects.get(nombre=self.semestre_nombre)
        
        # Prefetch optimizations
        cursos = list(Curso.objects.filter(semestre=semestre)
                     .select_related('docente', 'carrera')
                     .prefetch_related('especialidades__grupo')
                     .order_by('id'))
                     
        franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        # We only need one generic aula since we are optimizing "Aula" dimension out
        aulas = list(Aula.objects.all())
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        # Map: Group Key (semestre_cursado, grupo_id) -> List[curso_id]
        # This allows us to enforce: "Students in (Semestre 3, Group A) cannot be in two places at once"
        grupos_map = {}
        for c in cursos:
            # We assume a course belongs to the groups of its specialties
            # If a course has multiple groups, it might be a shared course or need specific handling.
            # For this logic, we check all connected groups.
            if c.semestre_cursado:
                # If course is connected to specific groups (Especialidad -> Grupo)
                groups = list(c.especialidades.all())
                if groups:
                    for esp in groups:
                        if esp.grupo:
                            key = (c.semestre_cursado, esp.grupo.id)
                            if key not in grupos_map:
                                grupos_map[key] = []
                            grupos_map[key].append(c.id)
                else:
                    # General course or no specific group linked (e.g. common core)
                    pass

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
            'no_lectivos': no_lectivos,
            'grupos_map': grupos_map
        }

    def _get_block_splits(self, total_hours):
        """
        Returns a list of block durations that sum up to total_hours.
        Strategies:
        4h -> [2, 2]
        5h -> [3, 2]
        6h -> [3, 3]
        7h -> [3, 2, 2]
        """
        if total_hours == 4:
            return [2, 2]
        elif total_hours == 5:
            return [3, 2]
        elif total_hours == 6:
            return [3, 3]
        elif total_hours == 7:
            return [3, 2, 2]
        elif total_hours == 8:
            return [4, 4] 
        elif total_hours <= 3:
            return [total_hours]
        else:
            # Fallback for > 8 or other weird numbers: splits of 2
            splits = []
            rem = total_hours
            while rem > 0:
                take = min(rem, 2)
                splits.append(take)
                rem -= take
            return splits

    def solve(self):
        cursos = self.data['cursos']
        franjas = self.data['franjas']
        dias = self.data['dias'] # Strings
        dias_idx = range(len(dias)) # 0..4
        num_franjas = len(franjas)
        
        # Variables: x[c_id, split_idx, duration, d_idx, f_start_idx]
        self.vars = {} 
        
        # 1. GENERATE VARIABLES & BLOCK CONSTRAINT
        
        for c in cursos:
            splits = self._get_block_splits(c.horas_academicas_semanales)
            
            for s_idx, duration in enumerate(splits):
                # Generate valid (day, start_slot) pairs
                assigned_vars = []
                
                for d in dias_idx:
                    # Identify valid start slots for this duration
                    for f in range(num_franjas - duration + 1):
                        
                        # Apply Hard Domain Constraints (Semester Turns)
                        block_slots = franjas[f : f+duration]
                        is_valid_turn = True
                        
                        if c.semestre_cursado:
                            if c.semestre_cursado <= 4 and not c.excepcion_horario:
                                if any(fs.turno != "MANANA" for fs in block_slots):
                                    is_valid_turn = False
                            elif c.semestre_cursado >= 5:
                                if any(fs.turno == "MANANA" for fs in block_slots):
                                    is_valid_turn = False
                        
                        if not is_valid_turn:
                            continue
                            
                        # Administrative / No-Lectivo Check
                        is_blocked_by_admin = False
                        if c.docente_id and c.docente_id in self.data['no_lectivos']:
                            teacher_no_lectivos = self.data['no_lectivos'][c.docente_id]
                            current_day_str = dias[d]
                            
                            for (bnl_dia, bnl_f_id, bnl_dur) in teacher_no_lectivos:
                                if bnl_dia == current_day_str:
                                    try:
                                        bnl_start_idx = next(i for i, fr in enumerate(franjas) if fr.id == bnl_f_id)
                                        bnl_end_idx = bnl_start_idx + bnl_dur
                                        
                                        # Overlap check
                                        if f < bnl_end_idx and (f + duration) > bnl_start_idx:
                                            is_blocked_by_admin = True
                                            break
                                    except StopIteration:
                                        pass
                        
                        if is_blocked_by_admin:
                            continue

                        # Create Variable
                        var_name = f'x_c{c.id}_s{s_idx}_d{d}_f{f}'
                        var = self.model.NewBoolVar(var_name)
                        
                        key = (c.id, s_idx, duration, d, f)
                        self.vars[key] = var
                        assigned_vars.append(var)

                # Constraint 1: Exactly one assignment for this split
                if assigned_vars:
                    self.model.Add(sum(assigned_vars) == 1)
                else:
                    print(f"WARNING: No valid slots for Course {c} Split {s_idx} ({duration}h)")
                    return None

        # Helper to get all variables active at a specific (day, slot)
        # Map: (day, slot) -> list of vars covering this slot
        vars_at_slot = {} 
        
        for (c_id, s_idx, duration, d, f), var in self.vars.items():
            for offset in range(duration):
                slot_idx = f + offset
                if slot_idx < num_franjas:
                    k = (d, slot_idx)
                    if k not in vars_at_slot:
                        vars_at_slot[k] = []
                    
                    course_obj = next(c for c in cursos if c.id == c_id)
                    vars_at_slot[k].append({
                        'var': var,
                        'c_id': c_id,
                        'docente_id': course_obj.docente_id,
                        'semestre': course_obj.semestre_cursado
                    })

        # Constraint 3: Teacher Conflicts (Max 1 per teacher per slot)
        docentes_ids = set(c.docente_id for c in cursos if c.docente_id)
        for d in dias_idx:
            for f in range(num_franjas):
                k = (d, f)
                if k not in vars_at_slot:
                    continue
                
                active_vars = vars_at_slot[k]
                
                for t_id in docentes_ids:
                    teacher_vars = [item['var'] for item in active_vars if item['docente_id'] == t_id]
                    if len(teacher_vars) > 1:
                        self.model.Add(sum(teacher_vars) <= 1)

        # Constraint 4: Student/Group Conflicts (Max 1 per Group per slot)
        for key, course_ids_in_group in self.data['grupos_map'].items():
            group_course_set = set(course_ids_in_group)
            
            for d in dias_idx:
                for f in range(num_franjas):
                    k = (d, f)
                    if k not in vars_at_slot:
                        continue
                        
                    active_vars = vars_at_slot[k]
                    group_vars = [item['var'] for item in active_vars if item['c_id'] in group_course_set]
                    
                    if len(group_vars) > 1:
                        self.model.Add(sum(group_vars) <= 1)
                        
        # Constraint 2 & 5: Teacher Daily Load and Course Daily Presence
        vars_by_course_day = {} # (c_id, d) -> list of vars
        vars_by_teacher_day = {} # (t_id, d) -> list of (var, start_f, duration)
        
        for (c_id, s_idx, duration, d, f), var in self.vars.items():
            # For Course Daily Limit
            cd_key = (c_id, d)
            if cd_key not in vars_by_course_day:
                vars_by_course_day[cd_key] = []
            vars_by_course_day[cd_key].append(var)
            
            # For Teacher Daily Load & Gaps
            course_obj = next(c for c in cursos if c.id == c_id)
            if course_obj.docente_id:
                td_key = (course_obj.docente_id, d)
                if td_key not in vars_by_teacher_day:
                    vars_by_teacher_day[td_key] = []
                vars_by_teacher_day[td_key].append((var, f, duration))

        # Apply C2: Max 1 session per day per course
        for cd_key, var_list in vars_by_course_day.items():
            if len(var_list) > 1:
                self.model.Add(sum(var_list) <= 1)

        # Apply C5: Max 8 hours per day per teacher
        for td_key, var_data in vars_by_teacher_day.items():
            self.model.Add(
                sum(v * dur for v, _, dur in var_data) <= 8
            )

        # ---------------------------------------------------------------------
        # OBJECTIVE FUNCTION: GAP MINIMIZATION
        # ---------------------------------------------------------------------
        total_gaps = []
        
        # Iterate over each teacher and each day
        for t_id in docentes_ids:
            for d in dias_idx:
                td_key = (t_id, d)
                
                # If teacher has no potential classes this day, gap is 0
                if td_key not in vars_by_teacher_day:
                    continue
                    
                assignments = vars_by_teacher_day[td_key]
                # assignments is list of (var, start_f, duration)
                
                # Aux variables for Min Slot and Max Slot
                # Domain: [-1, num_franjas]
                min_slot = self.model.NewIntVar(0, num_franjas, f'min_slot_t{t_id}_d{d}')
                max_slot = self.model.NewIntVar(-1, num_franjas, f'max_slot_t{t_id}_d{d}')
                
                # Lists to hold candidate start/end times
                start_candidates = []
                end_candidates = []
                
                # Indicator if teacher is active this day (has at least one class)
                # is_present = sum(vars) >= 1
                # But since C2/Course logic forces blocks, we can just sum variables
                teacher_vars = [v for v, _, _ in assignments]
                is_present = self.model.NewBoolVar(f'present_t{t_id}_d{d}')
                self.model.Add(sum(teacher_vars) >= 1).OnlyEnforceIf(is_present)
                self.model.Add(sum(teacher_vars) == 0).OnlyEnforceIf(is_present.Not())

                for var, start_f, duration in assignments:
                    # If this block is chosen:
                    #   candidate_start = start_f
                    #   candidate_end = start_f + duration - 1
                    # If NOT chosen:
                    #   candidate_start = num_franjas (to be ignored by Min)
                    #   candidate_end = -1 (to be ignored by Max)
                    
                    s_cand = self.model.NewIntVar(0, num_franjas, '')
                    e_cand = self.model.NewIntVar(-1, num_franjas, '')
                    
                    self.model.Add(s_cand == start_f).OnlyEnforceIf(var)
                    self.model.Add(s_cand == num_franjas).OnlyEnforceIf(var.Not())
                    
                    self.model.Add(e_cand == start_f + duration - 1).OnlyEnforceIf(var)
                    self.model.Add(e_cand == -1).OnlyEnforceIf(var.Not())
                    
                    start_candidates.append(s_cand)
                    end_candidates.append(e_cand)
                
                # Define Min/Max from candidates
                self.model.AddMinEquality(min_slot, start_candidates)
                self.model.AddMaxEquality(max_slot, end_candidates)
                
                # Calculate Span: (Max - Min + 1) if present, else 0
                span = self.model.NewIntVar(0, num_franjas, f'span_t{t_id}_d{d}')
                
                # If Present: Span = max - min + 1
                # We need an optimized way to express this linear dependency?
                # Actually, simply:
                # If is_present: min <= max (normal indices). span = max - min + 1
                # If NOT present: min = num_franjas, max = -1. 
                # span MUST be 0.
                
                self.model.Add(span == max_slot - min_slot + 1).OnlyEnforceIf(is_present)
                self.model.Add(span == 0).OnlyEnforceIf(is_present.Not())
                
                # Calculate Worked Hours
                worked_hours = self.model.NewIntVar(0, 8, f'worked_t{t_id}_d{d}')
                self.model.Add(worked_hours == sum(v * dur for v, _, dur in assignments))
                
                # Calculate Gap: Span - Worked Hours
                # If not present, Span=0, Worked=0 => Gap=0.
                gap = self.model.NewIntVar(0, num_franjas, f'gap_t{t_id}_d{d}')
                self.model.Add(gap == span - worked_hours)
                
                total_gaps.append(gap)
                
        # Minimize Total Gaps
        if total_gaps:
             self.model.Minimize(sum(total_gaps))
        
        # Set Time Limit (Soft Limit)
        self.solver.parameters.max_time_in_seconds = 60.0

        # SOLVE
        status = self.solver.Solve(self.model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return self._extract_results(cursos, franjas, dias)
        else:
            return None

    def _extract_results(self, cursos, franjas, dias):
        results = []
        
        # We need a fallback aula
        default_aula = self.data['aulas'][0] if self.data['aulas'] else None
        
        for (c_id, s_idx, duration, d, f), var in self.vars.items():
            if self.solver.Value(var) == 1:
                c_obj = next(c for c in cursos if c.id == c_id)
                f_obj = franjas[f]
                d_str = dias[d]
                
                results.append({
                    'curso': c_obj,
                    'dia': d_str,
                    'franja': f_obj,
                    'duracion': duration,
                    'aula': default_aula # Placeholder
                })
        return results

    @transaction.atomic
    def save_results(self, results):
        if not results:
            return False
            
        semestre = Semestre.objects.get(nombre=self.semestre_nombre)
        # Delete old blocks
        BloqueHorario.objects.filter(curso__semestre=semestre).delete()
        
        for r in results:
            BloqueHorario.objects.create(
                curso=r['curso'],
                dia=r['dia'],
                franja_inicio=r['franja'],
                aula=r['aula'],
                duracion_bloques=r['duracion']
            )
            
        return True
