from datetime import time
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import BloqueHorario, ConfiguracionInstitucion, Curso, FranjaHoraria, Semestre, Carrera, Especialidad, Grupo, Docente, Aula, BloqueNoLectivo

class RobustSchedulingTests(TestCase):
    def setUp(self):
        # Setup basic data
        self.config = ConfiguracionInstitucion.objects.create(
            nombre_institucion="Robust Scheduler Test",
            logo="configuracion/test.png",
            max_horas_diarias_docente=10,
            max_horas_diarias_especialidad=10,
            max_bloques_consecutivos_docente=5,
        )
        self.semestre = Semestre.objects.create(
            nombre="2024-I",
            fecha_inicio="2024-01-01",
            fecha_fin="2024-06-30",
            estado="ACTIVO"
        )
        self.grupo_a = Grupo.objects.create(nombre="Grupo A")
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Sistemas")
        self.especialidad = Especialidad.objects.create(nombre="Sistemas", grupo=self.grupo_a)
        self.docente = Docente.objects.create(username="docente_test", dni="11111111", first_name="Juan", last_name="Perez", disponibilidad="MANANA")
        self.aula = Aula.objects.create(nombre="Aula 101")

        self.curso = Curso.objects.create(
            nombre="Curso Test",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre,
            semestre_cursado=1,
            horas_academicas_semanales=10 # Sufficient for load tests
        )
        self.curso.especialidades.add(self.especialidad)

        self.franja_8am = FranjaHoraria.objects.create(turno="MANANA", hora_inicio=time(8, 0), hora_fin=time(8, 50))
        self.franja_9am = FranjaHoraria.objects.create(turno="MANANA", hora_inicio=time(8, 50), hora_fin=time(9, 40))

        # Create many slots for load testing
        self.franjas = [self.franja_8am, self.franja_9am]
        current_time = 9
        for i in range(10): # Create more slots
            f = FranjaHoraria.objects.create(
                turno="MANANA",
                hora_inicio=time(current_time, 0),
                hora_fin=time(current_time, 50)
            )
            self.franjas.append(f)
            current_time += 1

    def test_aula_conflict(self):
        """Test that an Aula cannot be double booked."""
        BloqueHorario.objects.create(
            curso=self.curso,
            dia="Lunes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1,
            aula=self.aula
        )

        # Another course trying to use same aula at same time
        esp2 = Especialidad.objects.create(nombre="Sis2", grupo=Grupo.objects.create(nombre="GB"))
        curso2 = Curso.objects.create(
            nombre="Curso 2", carrera=self.carrera, semestre=self.semestre, semestre_cursado=1,
            docente=Docente.objects.create(username="doc2", dni="22222222"),
        )
        curso2.especialidades.add(esp2)

        bloque_conflictivo = BloqueHorario(
            curso=curso2,
            dia="Lunes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1,
            aula=self.aula
        )

        with self.assertRaises(ValidationError) as cm:
            bloque_conflictivo.clean()
        self.assertIn("aula", str(cm.exception))

    def test_bloque_no_lectivo_conflict(self):
        """Test conflict between class and non-teaching block."""
        BloqueNoLectivo.objects.create(
            docente=self.docente,
            dia="Martes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1,
            motivo="Reunión"
        )

        bloque_clase = BloqueHorario(
            curso=self.curso,
            dia="Martes",
            franja_inicio=self.franja_8am,
            duracion_bloques=1
        )

        with self.assertRaises(ValidationError) as cm:
            bloque_clase.clean()
        self.assertIn("bloque no lectivo", str(cm.exception))

    def test_student_daily_load_limit(self):
        """Test configurable max 6 hours per day for student group."""
        self.config.max_horas_diarias_especialidad = 6
        self.config.save(update_fields=["max_horas_diarias_especialidad"])

        # Assign 6 hours
        for i in range(6):
            BloqueHorario.objects.create(
                curso=self.curso,
                dia="Miércoles",
                franja_inicio=self.franjas[i],
                duracion_bloques=1
            )

        # Try 7th hour
        bloque_exceso = BloqueHorario(
            curso=self.curso,
            dia="Miércoles",
            franja_inicio=self.franjas[6],
            duracion_bloques=1
        )

        with self.assertRaises(ValidationError) as cm:
            bloque_exceso.clean()
        self.assertIn("excede el límite de 6 horas", str(cm.exception))

    def test_teacher_daily_load_limit(self):
        """Test configurable max 8 hours per day for teacher."""
        self.config.max_horas_diarias_docente = 8
        self.config.save(update_fields=["max_horas_diarias_docente"])

        # Assign 8 hours
        for i in range(8):
            BloqueHorario.objects.create(
                curso=self.curso,
                dia="Jueves",
                franja_inicio=self.franjas[i],
                duracion_bloques=1
            )

        # Try 9th hour
        bloque_exceso = BloqueHorario(
            curso=self.curso,
            dia="Jueves",
            franja_inicio=self.franjas[8],
            duracion_bloques=1
        )

        with self.assertRaises(ValidationError) as cm:
            bloque_exceso.clean()
        self.assertIn("excede el límite de 8 horas", str(cm.exception))

    def test_continuous_load_limit(self):
        """Test configurable max consecutive blocks for teacher."""
        self.config.max_bloques_consecutivos_docente = 4
        self.config.save(update_fields=["max_bloques_consecutivos_docente"])

        bloque_largo = BloqueHorario(
            curso=self.curso,
            dia="Viernes",
            franja_inicio=self.franja_8am,
            duracion_bloques=5
        )

        with self.assertRaises(ValidationError) as cm:
            bloque_largo.clean()
        self.assertIn("4 bloques consecutivos", str(cm.exception))
