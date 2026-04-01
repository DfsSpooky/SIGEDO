from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from core.models import BloqueHorario, Carrera, Curso, Docente, Especialidad, FranjaHoraria, Grupo, Semestre


class PlannerExportTest(TestCase):
    def setUp(self):
        self.admin = Docente.objects.create_user(
            username="admin_export",
            password="password123",
            dni="12121212",
            is_staff=True,
        )
        self.client.login(username="admin_export", password="password123")

        self.semestre = Semestre.objects.create(
            nombre="2026-A",
            tipo="IMPAR",
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 7, 31),
            estado="ACTIVO",
        )
        self.carrera = Carrera.objects.create(nombre="Ingenieria de Sistemas")
        self.grupo = Grupo.objects.create(nombre="Grupo A")
        self.especialidad = Especialidad.objects.create(
            nombre="Desarrollo de Software",
            grupo=self.grupo,
        )
        self.docente = Docente.objects.create_user(
            username="docente_export",
            password="password123",
            dni="34343434",
            first_name="Ana",
            last_name="Perez",
        )

        self.franja = FranjaHoraria.objects.create(
            turno="MANANA",
            hora_inicio=time(8, 0),
            hora_fin=time(8, 50),
        )
        self.franja_2 = FranjaHoraria.objects.create(
            turno="MANANA",
            hora_inicio=time(9, 0),
            hora_fin=time(9, 50),
        )

        self.curso = Curso.objects.create(
            nombre="Arquitectura de Software",
            tipo_curso="ESPECIALIDAD",
            docente=self.docente,
            carrera=self.carrera,
            semestre=self.semestre,
            semestre_cursado=1,
            horas_academicas_semanales=2,
        )
        self.curso.especialidades.add(self.especialidad)

        BloqueHorario.objects.create(
            curso=self.curso,
            dia="Lunes",
            franja_inicio=self.franja,
            duracion_bloques=2,
        )

    def test_exportar_horario_actual(self):
        response = self.client.get(
            reverse("api_exportar_horario"),
            {"tipo": "actual", "especialidad_id": self.especialidad.id, "semestre": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horario de Clases")
        self.assertContains(response, "Desarrollo de Software")
        self.assertContains(response, "Arquitectura de Software")

    def test_exportar_horarios_por_carrera(self):
        response = self.client.get(reverse("api_exportar_horario"), {"tipo": "carrera"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horarios por Carrera")
        self.assertContains(response, "Ingenieria de Sistemas")
        self.assertContains(response, "Desarrollo de Software")

    def test_exportar_horarios_por_docente(self):
        response = self.client.get(reverse("api_exportar_horario"), {"tipo": "docente"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horarios por Docente")
        self.assertContains(response, "Ana Perez")
        self.assertContains(response, "Arquitectura de Software")
