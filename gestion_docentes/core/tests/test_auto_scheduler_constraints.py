from datetime import time
from django.test import TestCase
from django.db import models
from core.models import BloqueHorario, ConfiguracionInstitucion, Curso, FranjaHoraria, Semestre, Carrera, Especialidad, Grupo, Docente, BloqueNoLectivo, Aula
from core.api.views.planner import generar_horario_automatico
from django.test.client import RequestFactory
from django.contrib.auth.models import AnonymousUser
from unittest.mock import Mock

class AutoSchedulerConstraintsTests(TestCase):
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
        self.docente = Docente.objects.create(username="docente_auto", dni="33333333", first_name="Juan", last_name="Auto", disponibilidad="MANANA")
        self.admin = Docente.objects.create(username="admin", dni="99999999", is_staff=True)
        self.config = ConfiguracionInstitucion.objects.create(
            nombre_institucion="Test Scheduler",
            logo="configuracion/test.png",
            max_horas_diarias_docente=10,
            max_horas_diarias_especialidad=10,
            max_bloques_consecutivos_docente=5,
        )

        # Create many time slots (10 slots)
        self.franjas = []
        current_time = 8
        for i in range(10):
            f = FranjaHoraria.objects.create(
                turno="MANANA",
                hora_inicio=time(current_time, 0),
                hora_fin=time(current_time, 50)
            )
            self.franjas.append(f)
            current_time += 1

        # Course with excessive hours (15 hours) -> needs 3 hours/day if M-F, but max is 2 slots/day usually if evenly distributed.
        # Let's try to force exceeding daily limit.
        # Max load is 8h/day. If we have a course with 45 hours/week (impossible but for test), it should fail or spread out.
        # Let's create a scenario where Non-Teaching block blocks Monday, so all hours must go to T-F.

        self.curso_pesado = Curso.objects.create(
            nombre="Curso Pesado",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre,
            semestre_cursado=1,
            horas_academicas_semanales=10
        )
        self.curso_pesado.especialidades.add(self.especialidad)

        self.factory = RequestFactory()

    def test_auto_scheduler_respects_non_teaching_blocks(self):
        """
        Create a Non-Teaching Block for the teacher on Monday 8:00-12:00.
        Run auto-scheduler.
        Ensure no class is assigned to Monday morning.
        """
        # Block Monday first 4 slots
        BloqueNoLectivo.objects.create(
            docente=self.docente,
            dia="Lunes",
            franja_inicio=self.franjas[0],
            duracion_bloques=4,
            motivo="Gestión"
        )

        request = self.factory.post('/api/auto-schedule/')
        request.user = self.admin

        # Run generator
        response = generar_horario_automatico(request)
        self.assertEqual(response.status_code, 200)

        # Verify no blocks on Monday morning for this course
        lunes_bloques = BloqueHorario.objects.filter(
            curso=self.curso_pesado,
            dia="Lunes"
        )

        # Since we blocked the first 4 slots (8am-11:20am), and we only have slots from 8am onwards defined in setup.
        # The auto scheduler might assign later in the day if slots exist.
        # Let's check specifically for overlap with the blocked time.

        start_time_blocked = self.franjas[0].hora_inicio
        end_time_blocked = self.franjas[3].hora_fin # 4th slot end

        for bloque in lunes_bloques:
            # Re-calculate times for the block found
            start_b, end_b = bloque._calculate_times()
            # Check overlap
            if start_b < end_time_blocked and end_b > start_time_blocked:
                self.fail(f"Auto-scheduler assigned block overlapping with Non-Teaching Block: {bloque}")

    def test_auto_scheduler_respects_daily_limits(self):
        """
        Create a course with enough hours that forces a dense schedule.
        Ensure the generator still respects daily and consecutive-load limits.
        """
        # 40 hours/week course (extreme case)
        self.curso_pesado.horas_academicas_semanales = 40
        self.curso_pesado.save()

        # We need enough slots in DB for this to even be possible. We have 10 slots * 5 days = 50 slots.
        # Teacher limit is 8h/day. So max 40h/week is possible (8*5).
        # If we reduce slots or add blocks, it should fail to assign completely but NOT exceed daily limit.

        request = self.factory.post('/api/auto-schedule/')
        request.user = self.admin

        response = generar_horario_automatico(request)
        self.assertEqual(response.status_code, 200)

        for dia in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]:
            bloques_dia = list(
                BloqueHorario.objects.filter(
                    curso__docente=self.docente,
                    dia=dia
                ).order_by("franja_inicio__hora_inicio")
            )

            horas = sum(b.duracion_bloques for b in bloques_dia)
            self.assertLessEqual(horas, 10, f"Teacher daily limit exceeded on {dia}: {horas}")

            slots = []
            for bloque in bloques_dia:
                start_idx = self.franjas.index(bloque.franja_inicio)
                slots.extend(range(start_idx, start_idx + bloque.duracion_bloques))

            max_consecutive = 0
            current = 0
            prev = None
            for slot in sorted(slots):
                if prev is not None and slot == prev + 1:
                    current += 1
                else:
                    current = 1
                prev = slot
                max_consecutive = max(max_consecutive, current)

            self.assertLessEqual(
                max_consecutive,
                self.config.max_bloques_consecutivos_docente,
                f"Teacher consecutive limit exceeded on {dia}: {max_consecutive}",
            )
