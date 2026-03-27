from datetime import time
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import BloqueHorario, Curso, FranjaHoraria, Semestre, Carrera, Especialidad, Grupo, Docente

class SchedulerConflictTests(TestCase):
    def setUp(self):
        # Setup basic data
        self.semestre = Semestre.objects.create(
            nombre="2024-I",
            fecha_inicio="2024-01-01",
            fecha_fin="2024-06-30",
            estado="ACTIVO"
        )
        self.grupo_a = Grupo.objects.create(nombre="Grupo A")
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Sistemas")
        self.especialidad = Especialidad.objects.create(nombre="Sistemas", grupo=self.grupo_a)

        # Docentes
        self.docente1 = Docente.objects.create(username="docente1", dni="12345678", first_name="Juan", last_name="Perez", email="juan@example.com", disponibilidad="MANANA")
        self.docente2 = Docente.objects.create(username="docente2", dni="87654321", first_name="Maria", last_name="Gomez", email="maria@example.com", disponibilidad="MANANA")

        # Cursos (Same Semester, Same Group)
        self.curso_computacion = Curso.objects.create(
            nombre="Computación",
            docente=self.docente1,
            carrera=self.carrera,
            semestre=self.semestre,
            semestre_cursado=1,
            tipo_curso="ESPECIALIDAD",
            horas_academicas_semanales=4
        )
        self.curso_computacion.especialidades.add(self.especialidad)

        self.curso_fisica = Curso.objects.create(
            nombre="Educación Física",
            docente=self.docente2,
            carrera=self.carrera,
            semestre=self.semestre,
            semestre_cursado=1,
            tipo_curso="ESPECIALIDAD",
            horas_academicas_semanales=2
        )
        self.curso_fisica.especialidades.add(self.especialidad)

        # Franja Horaria (8:00 - 8:50)
        self.franja_8am = FranjaHoraria.objects.create(
            turno="MANANA",
            hora_inicio=time(8, 0),
            hora_fin=time(8, 50)
        )

        # Franja Horaria (8:50 - 9:40)
        self.franja_9am = FranjaHoraria.objects.create(
            turno="MANANA",
            hora_inicio=time(8, 50),
            hora_fin=time(9, 40)
        )

    def test_grupo_conflict_same_time(self):
        """
        Test that two courses for the same Group (A) and Semester (1) cannot be scheduled at the same time.
        """
        # Assign Computacion to Monday 8:00 AM
        BloqueHorario.objects.create(
            curso=self.curso_computacion,
            dia="Lunes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1
        )

        # Try to assign Fisica to Monday 8:00 AM (Same Group, Same Semester -> Should Fail)
        bloque_conflictivo = BloqueHorario(
            curso=self.curso_fisica,
            dia="Lunes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1
        )

        # Expect ValidationError
        with self.assertRaises(ValidationError) as cm:
            bloque_conflictivo.clean()

        self.assertIn("Conflicto de Grupo", str(cm.exception))

    def test_docente_conflict_same_time(self):
        """
        Test that the same teacher cannot teach two different courses at the same time.
        """
        # Create another course for Docente 1 (in a different group/semester to isolate teacher conflict)
        grupo_b = Grupo.objects.create(nombre="Grupo B")
        especialidad_b = Especialidad.objects.create(nombre="Sistemas B", grupo=grupo_b)

        curso_otro = Curso.objects.create(
            nombre="Programación Avanzada",
            docente=self.docente1, # Same teacher as Computacion
            carrera=self.carrera,
            semestre=self.semestre,
            semestre_cursado=3,
            tipo_curso="ESPECIALIDAD"
        )
        curso_otro.especialidades.add(especialidad_b)

        # Assign Computacion to Tuesday 8:00 AM
        BloqueHorario.objects.create(
            curso=self.curso_computacion,
            dia="Martes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1
        )

        # Try to assign Programacion Avanzada to Tuesday 8:00 AM (Same Teacher -> Should Fail)
        bloque_conflictivo = BloqueHorario(
            curso=curso_otro,
            dia="Martes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1
        )

        # Expect ValidationError
        with self.assertRaises(ValidationError) as cm:
            bloque_conflictivo.clean()

        self.assertIn("ya tiene clase asignada en este horario", str(cm.exception))
