import datetime
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password
from core.models import Semestre, Carrera, Especialidad, Grupo, Aula, FranjaHoraria, Docente, Curso, BloqueHorario, BloqueNoLectivo
from ortools.sat.python import cp_model

class Command(BaseCommand):
    help = 'Script completo: Inicializa DB, carga datos de los PDFs y genera el horario 2026-A con OR-Tools'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- INICIANDO PROCESO COMPLETO DE HORARIOS 2026-A ---'))
        
        with transaction.atomic():
            self.limpiar_datos_viejos()
            self.inicializar_base()
            self.cargar_datos_pdfs()
            
            # self.generar_horario_con_ia()

    def limpiar_datos_viejos(self):
        self.stdout.write('1. Limpiando datos de prueba anteriores...')
        BloqueHorario.objects.all().delete()
        BloqueNoLectivo.objects.all().delete()
        Curso.objects.all().delete()

    def inicializar_base(self):
        self.stdout.write('2. Creando Semestre, Franjas, Grupos y Aulas...')
        
        # Semestre 2026-A
        self.semestre, _ = Semestre.objects.get_or_create(
            nombre="2026-A", defaults={'fecha_inicio': datetime.date(2026, 3, 23), 'fecha_fin': datetime.date(2026, 7, 24), 'estado': 'ACTIVO', 'tipo': 'IMPAR'}
        )
        
        # Franjas Horarias (Bloques de 50 min)
        franjas_data = [
            ("MANANA", 8, 0, 8, 50), ("MANANA", 8, 50, 9, 40), ("MANANA", 9, 40, 10, 30),
            ("MANANA", 10, 30, 11, 20), ("MANANA", 11, 20, 12, 10), ("MANANA", 12, 10, 13, 0),
            ("TARDE", 14, 0, 14, 50), ("TARDE", 14, 50, 15, 40), ("TARDE", 15, 40, 16, 30),
            ("TARDE", 16, 30, 17, 20), ("TARDE", 17, 20, 18, 10), ("TARDE", 18, 10, 19, 0),
            ("TARDE", 19, 0, 19, 50), ("TARDE", 19, 50, 20, 40)
        ]
        self.franjas_manana = []
        self.franjas_tarde = []
        for turno, h1, m1, h2, m2 in franjas_data:
            f, _ = FranjaHoraria.objects.get_or_create(hora_inicio=datetime.time(h1, m1), defaults={'turno': turno, 'hora_fin': datetime.time(h2, m2)})
            if turno == "MANANA": self.franjas_manana.append(f)
            else: self.franjas_tarde.append(f)

        # Carrera y Especialidades
        self.carrera, _ = Carrera.objects.get_or_create(nombre="Educación Secundaria")
        self.grupo_a, _ = Grupo.objects.get_or_create(nombre="A")
        self.grupo_b, _ = Grupo.objects.get_or_create(nombre="B")
        self.grupo_c, _ = Grupo.objects.get_or_create(nombre="C")
        
        esp_nombres = ["Biología y Química", "Lenguas Extranjeras: Inglés - Francés", "Tecnología Informática", "Historia", "Filosofía", "Comunicación y Literatura"]
        self.especialidades = {}
        for esp in esp_nombres:
            e, _ = Especialidad.objects.get_or_create(nombre=esp, defaults={'grupo': self.grupo_a})
            self.especialidades[esp] = e

        # Aulas
        self.aulas = [Aula.objects.get_or_create(nombre=f"Pabellón A - {i}", defaults={'es_laboratorio': False})[0] for i in range(101, 106)]

    def cargar_datos_pdfs(self):
        self.stdout.write('3. Cargando Docentes y Cursos Reales de los PDFs 2026-A...')
        
        # DATOS EXACTOS DE TUS PDFs
        pdf_data = [
            # LITERATURA
            {"dni": "10000001", "nombre": "David Elí", "apellido": "SALAZAR ESPINOZA", "cat": "Principal D.E.", 
             "cursos": [("Literatura Peruana II", 7, 5, "Comunicación y Literatura", self.grupo_b)], 
             "admin": [("Investigación", 25), ("Preparación", 5)]},
             
            # LENGUAS EXTRANJERAS
            {"dni": "20000001", "nombre": "Edith Nelly", "apellido": "ZELA SANCHEZ", "cat": "Auxiliar T.C.", 
             "cursos": [("Inglés VIII", 9, 6, "Lenguas Extranjeras: Inglés - Francés", self.grupo_b), ("Traducción Inglés II", 7, 2, "Lenguas Extranjeras: Inglés - Francés", self.grupo_b)], 
             "admin": [("Preparación de clase", 10)]},
             
            # BIOLOGÍA
            {"dni": "30000001", "nombre": "Liz Ketty", "apellido": "BERNALDO FAUSTINO", "cat": "Auxiliar T.C.", 
             "cursos": [("Calidad Educativa", 7, 4, "Biología y Química", self.grupo_c), ("PPP I", 5, 4, "Biología y Química", self.grupo_c)], 
             "admin": [("Preparación de clase", 10)]},
             
            # HISTORIA
            {"dni": "40000001", "nombre": "Marcelino Erasmo", "apellido": "HUAMAN PANEZ", "cat": "Principal D.E.", 
             "cursos": [("Geografía Humana", 7, 7, "Historia", self.grupo_a), ("Sociología Política", 9, 6, "Historia", self.grupo_a)], 
             "admin": [("Preparación de clases", 9)]},
        ]

        for d in pdf_data:
            docente, _ = Docente.objects.get_or_create(
                dni=d['dni'], defaults={'username': f"{d['nombre'].split()[0].lower()}.{d['apellido'].split()[0].lower()}", 'first_name': d['nombre'], 'last_name': d['apellido'], 'password': make_password(d['dni'])}
            )
            for c_nom, sem, hrs, esp_nom, grupo in d['cursos']:
                curso = Curso.objects.create(nombre=c_nom, docente=docente, semestre=self.semestre, carrera=self.carrera, semestre_cursado=sem, horas_academicas_semanales=hrs)
                curso.especialidades.add(self.especialidades[esp_nom])
            
            # Asignar bloque no lectivo (admin) al final de la semana para que no moleste en el generador
            for motivo, horas in d['admin']:
                BloqueNoLectivo.objects.create(docente=docente, dia="Viernes", franja_inicio=self.franjas_tarde[-1], duracion_bloques=horas, motivo=motivo)

    def generar_horario_con_ia(self):
        self.stdout.write(self.style.SUCCESS('4. INICIANDO SOLVER DE OR-TOOLS... 🧠'))
        
        model = cp_model.CpModel()
        cursos = Curso.objects.all()
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        todas_franjas = self.franjas_manana + self.franjas_tarde
        num_franjas = len(todas_franjas)

        # Diccionario de variables: x[curso_id, dia, franja_idx]
        x = {}
        for c in cursos:
            for d in range(5):
                for f in range(num_franjas):
                    x[c.id, d, f] = model.NewBoolVar(f'c{c.id}_d{d}_f{f}')

        # RESTRICCIÓN 1: Carga Horaria Completa
        for c in cursos:
            model.Add(sum(x[c.id, d, f] for d in range(5) for f in range(num_franjas)) == c.horas_academicas_semanales)

        # RESTRICCIÓN 2: Sin cruces para el Docente
        docentes_map = defaultdict(list)
        for c in cursos: docentes_map[c.docente_id].append(c.id)
        
        for d_id, cursos_docente in docentes_map.items():
            for d in range(5):
                for f in range(num_franjas):
                    model.Add(sum(x[c_id, d, f] for c_id in cursos_docente) <= 1)

        # RESTRICCIÓN 3: Turnos por Semestre (Mañana vs Tarde)
        for c in cursos:
            # Semestres 1-4 SOLO MAÑANA (indices 0 a 5)
            if c.semestre_cursado <= 4:
                for d in range(5):
                    for f in range(6, num_franjas): # Franjas de tarde
                        model.Add(x[c.id, d, f] == 0)
            # Semestres 5-10 SOLO TARDE (indices 6 a 13)
            elif c.semestre_cursado >= 5:
                for d in range(5):
                    for f in range(0, 6): # Franjas de mañana
                        model.Add(x[c.id, d, f] == 0)

        # RESTRICCIÓN 4: Límite Diario Docente (Máx 8 horas)
        for d_id, cursos_docente in docentes_map.items():
            for d in range(5):
                model.Add(sum(x[c_id, d, f] for c_id in cursos_docente for f in range(num_franjas)) <= 8)

        # RESOLVER EL MODELO
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0 # Tiempo límite de búsqueda
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            self.stdout.write(self.style.SUCCESS('✅ ¡HORARIO GENERADO CON ÉXITO! Guardando en la base de datos...'))
            
            with transaction.atomic():
                for c in cursos:
                    for d in range(5):
                        for f in range(num_franjas):
                            if solver.Value(x[c.id, d, f]):
                                BloqueHorario.objects.create(
                                    curso=c,
                                    dia=dias[d],
                                    franja_inicio=todas_franjas[f],
                                    duracion_bloques=1,
                                    aula=self.aulas[0] # Asignación básica de aula
                                )
            self.stdout.write(self.style.SUCCESS('--- SISTEMA LISTO. REVISA EL FRONTEND ---'))
        else:
            self.stdout.write(self.style.ERROR('❌ No se encontró una solución factible. Revisa las restricciones.'))