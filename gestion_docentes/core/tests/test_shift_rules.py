from datetime import date, time, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Curso, BloqueHorario, FranjaHoraria, Carrera, Semestre, Docente, Grupo, Especialidad

class ShiftRulesTest(TestCase):
    def setUp(self):
        self.docente = Docente.objects.create_user(username="profesor_turno", password="password", dni="12345678")
        self.semestre_obj = Semestre.objects.create(
            nombre="Semestre 2024-I",
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=120),
            estado="ACTIVO"
        )
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Software")
        self.grupo = Grupo.objects.create(nombre="A")
        self.especialidad = Especialidad.objects.create(nombre="Ing. Software", grupo=self.grupo)

        # Franjas Horarias
        self.franja_manana = FranjaHoraria.objects.create(turno="MANANA", hora_inicio=time(8, 0), hora_fin=time(8, 50))
        self.franja_tarde = FranjaHoraria.objects.create(turno="TARDE", hora_inicio=time(14, 0), hora_fin=time(14, 50))

    def test_low_semester_morning_success(self):
        """Semester 1-4 allowed in Morning."""
        curso = Curso.objects.create(
            nombre="Matemática I",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre_obj,
            semestre_cursado=1,
            horas_academicas_semanales=2
        )
        bloque = BloqueHorario(
            curso=curso,
            dia="Lunes",
            franja_inicio=self.franja_manana,
            duracion_bloques=1
        )
        # Should not raise
        bloque.full_clean()
        bloque.save()

    def test_low_semester_afternoon_fail(self):
        """Semester 1-4 NOT allowed in Afternoon by default."""
        curso = Curso.objects.create(
            nombre="Matemática I",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre_obj,
            semestre_cursado=1,
            horas_academicas_semanales=2,
            excepcion_horario=False
        )
        bloque = BloqueHorario(
            curso=curso,
            dia="Martes",
            franja_inicio=self.franja_tarde,
            duracion_bloques=1
        )
        with self.assertRaises(ValidationError) as cm:
            bloque.full_clean()
        self.assertIn("deben dictarse en la MAÑANA", str(cm.exception))

    def test_low_semester_afternoon_exception_success(self):
        """Semester 1-4 allowed in Afternoon IF exception is True."""
        curso = Curso.objects.create(
            nombre="Matemática I (Recuperación)",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre_obj,
            semestre_cursado=1,
            horas_academicas_semanales=2,
            excepcion_horario=True
        )
        bloque = BloqueHorario(
            curso=curso,
            dia="Miércoles",
            franja_inicio=self.franja_tarde,
            duracion_bloques=1
        )
        # Should not raise
        bloque.full_clean()
        bloque.save()

    def test_high_semester_afternoon_success(self):
        """Semester 5-10 allowed in Afternoon."""
        curso = Curso.objects.create(
            nombre="Gestión de Proyectos",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre_obj,
            semestre_cursado=8,
            horas_academicas_semanales=2
        )
        bloque = BloqueHorario(
            curso=curso,
            dia="Jueves",
            franja_inicio=self.franja_tarde,
            duracion_bloques=1
        )
        # Should not raise
        bloque.full_clean()
        bloque.save()

    def test_high_semester_morning_fail(self):
        """Semester 5-10 NOT allowed in Morning."""
        curso = Curso.objects.create(
            nombre="Gestión de Proyectos",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre_obj,
            semestre_cursado=8,
            horas_academicas_semanales=2
        )
        bloque = BloqueHorario(
            curso=curso,
            dia="Viernes",
            franja_inicio=self.franja_manana,
            duracion_bloques=1
        )
        with self.assertRaises(ValidationError) as cm:
            bloque.full_clean()
        self.assertIn("deben dictarse en la TARDE", str(cm.exception))
