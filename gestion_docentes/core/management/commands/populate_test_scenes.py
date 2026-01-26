import random
from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from core.models import (
    Carrera,
    Curso,
    Docente,
    Especialidad,
    FranjaHoraria,
    Grupo,
    Semestre,
    BloqueHorario,
    Aula,
    BloqueNoLectivo
)

User = get_user_model()

class Command(BaseCommand):
    help = "Puebla la base de datos con escenearios de prueba estresantes para el Solver OR-Tools."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- INICIANDO POBLACIÓN DE ESCENARIOS DE PRUEBA ---'))

        # 1. Limpieza
        self.limpiar_datos()

        # 2. Infraestructura Básica (Semestre, Franjas, Aulas)
        semestre = self.crear_infraestructura()

        # 3. Escenario 1: Fragmentación (Cursos de 4h, 5h, 6h)
        self.crear_escenario_fragmentacion(semestre)

        # 4. Escenario 2: Cruces de Grupo (Estudiantes en dos sitios)
        self.crear_escenario_cruces_grupo(semestre)

        # 5. Escenario 3: Minimización de Huecos (Docente Ocupado)
        self.crear_escenario_huecos_docente(semestre)

        self.stdout.write(self.style.SUCCESS('--- POBLACIÓN DE PRUEBAS COMPLETADA ---'))

    def limpiar_datos(self):
        self.stdout.write("1. Limpiando DB...")
        BloqueHorario.objects.all().delete()
        BloqueNoLectivo.objects.all().delete()
        Curso.objects.all().delete()
        Docente.objects.all().delete()
        Especialidad.objects.all().delete()
        Grupo.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        Aula.objects.all().delete() # Limpiamos aulas también para tener control
        FranjaHoraria.objects.all().delete()

    def crear_infraestructura(self):
        self.stdout.write("2. Creando Infraestructura...")
        
        # Semestre
        semestre = Semestre.objects.create(
            nombre="2026-A",
            fecha_inicio=date(2026, 3, 23),
            fecha_fin=date(2026, 7, 24),
            estado="ACTIVO",
            tipo="IMPAR"
        )

        # Franjas (Mañana y Tarde)
        # Mañana: 08:00 - 13:00 (6 bloques)
        # Tarde: 14:00 - 20:00 (7 bloques)
        franjas_data = [
            ("MANANA", 8, 0, 8, 50), ("MANANA", 8, 50, 9, 40), ("MANANA", 9, 40, 10, 30),
            ("MANANA", 10, 30, 11, 20), ("MANANA", 11, 20, 12, 10), ("MANANA", 12, 10, 13, 0),
            ("TARDE", 14, 0, 14, 50), ("TARDE", 14, 50, 15, 40), ("TARDE", 15, 40, 16, 30),
            ("TARDE", 16, 30, 17, 20), ("TARDE", 17, 20, 18, 10), ("TARDE", 18, 10, 19, 0),
            ("TARDE", 19, 0, 19, 50)
        ]
        for turno, h1, m1, h2, m2 in franjas_data:
            FranjaHoraria.objects.create(
                turno=turno,
                hora_inicio=time(h1, m1),
                hora_fin=time(h2, m2)
            )

        # Aulas (Solo 2 para forzar competencia si fuera necesario, aunque el solver usa la generica)
        Aula.objects.create(nombre="Aula 101", es_laboratorio=False)
        Aula.objects.create(nombre="Aula 102", es_laboratorio=False)

        # Carrera
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Pruebas")

        return semestre

    def crear_docente(self, nombre, apellido, dni_suffix):
        return Docente.objects.create_user(
            username=f"{nombre.lower()}.{apellido.lower()}",
            password="123",
            first_name=nombre,
            last_name=apellido,
            dni=f"8888{dni_suffix}",
            disponibilidad="COMPLETO"
        )

    def crear_escenario_fragmentacion(self, semestre):
        self.stdout.write("   -> Escenario 1: Fragmentación (Block Splitting)")
        
        docente = self.crear_docente("Profesor", "Fragmentación", "001")
        grupo = Grupo.objects.create(nombre="Grupo Fragmentación")
        especialidad = Especialidad.objects.create(nombre="Esp Frag", grupo=grupo)

        # Curso 4 Horas -> Esperado: [2, 2]
        c4 = Curso.objects.create(
            nombre="Curso 4 Horas",
            docente=docente,
            semestre=semestre,
            carrera=self.carrera,
            semestre_cursado=1,
            horas_academicas_semanales=4, # [2, 2]
            tipo_curso="ESPECIALIDAD"
        )
        c4.especialidades.add(especialidad)

        # Curso 6 Horas -> Esperado: [3, 3]
        c6 = Curso.objects.create(
            nombre="Curso 6 Horas",
            docente=docente,
            semestre=semestre,
            carrera=self.carrera,
            semestre_cursado=1,
            horas_academicas_semanales=6, # [3, 3]
            tipo_curso="ESPECIALIDAD"
        )
        c6.especialidades.add(especialidad)

    def crear_escenario_cruces_grupo(self, semestre):
        self.stdout.write("   -> Escenario 2: Cruces de Grupo")
        
        # Grupo Semestre 3 (Mañana)
        grupo_a = Grupo.objects.create(nombre="Grupo A")
        esp_a = Especialidad.objects.create(nombre="Sistemas", grupo=grupo_a)
        
        docente1 = self.crear_docente("Profesor", "Conflicto1", "002")
        docente2 = self.crear_docente("Profesor", "Conflicto2", "003")

        # Dos cursos para el MISMO grupo (Sem 3, Grupo A)
        # Si el solver funciona, NO pueden estar a la misma hora aunque tengan profes distintos.
        
        c1 = Curso.objects.create(
            nombre="Curso Conflicto A",
            docente=docente1,
            semestre=semestre,
            carrera=self.carrera,
            semestre_cursado=3, # Mañana
            horas_academicas_semanales=4,
            tipo_curso="ESPECIALIDAD"
        )
        c1.especialidades.add(esp_a)

        c2 = Curso.objects.create(
            nombre="Curso Conflicto B",
            docente=docente2,
            semestre=semestre,
            carrera=self.carrera,
            semestre_cursado=3, # Mañana
            horas_academicas_semanales=4,
            tipo_curso="ESPECIALIDAD"
        )
        c2.especialidades.add(esp_a)

    def crear_escenario_huecos_docente(self, semestre):
        self.stdout.write("   -> Escenario 3: Minimización de Huecos")
        
        docente = self.crear_docente("Profesor", "Huecos", "004")
        grupo = Grupo.objects.create(nombre="Grupo Huecos")
        esp = Especialidad.objects.create(nombre="Esp Huecos", grupo=grupo)

        # Asignar varios cursos al mismo docente para llenar su día.
        # Si el solver minimiza huecos, debería ponerlos seguidos.
        
        # 3 cursos de 2 horas (6 horas total) en Semestre 1 (Mañana)
        for i in range(1, 4):
            c = Curso.objects.create(
                nombre=f"Curso Hueco {i}",
                docente=docente,
                semestre=semestre,
                carrera=self.carrera,
                semestre_cursado=1, # Mañana: Slots 0-5
                horas_academicas_semanales=2,
                tipo_curso="ESPECIALIDAD"
            )
            c.especialidades.add(esp)
