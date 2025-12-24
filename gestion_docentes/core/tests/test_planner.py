from core.models import (
    BloqueHorario,
    Carrera,
    Curso,
    Docente,
    Especialidad,
    FranjaHoraria,
    Grupo,
    Semestre,
)
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class PlannerApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Setup basic data
        self.semestre = Semestre.objects.create(
            nombre="2024-I",
            fecha_inicio="2024-03-01",
            fecha_fin="2024-07-01",
            estado="ACTIVO",
        )
        self.docente = Docente.objects.create_user(
            username="profesor1",
            password="password123",
            dni="11111111",
            first_name="Juan",
            last_name="Perez",
            is_staff=True,  # Required for the views
        )
        self.grupo = Grupo.objects.create(nombre="G1")
        self.especialidad = Especialidad.objects.create(
            nombre="Ingenieria", grupo=self.grupo
        )
        self.carrera = Carrera.objects.create(nombre="Software")
        self.curso = Curso.objects.create(
            nombre="Matematica",
            semestre=self.semestre,
            docente=self.docente,
            especialidad=self.especialidad,
            carrera=self.carrera,
            horas_academicas_semanales=4,
            semestre_cursado=1,
        )
        self.franja = FranjaHoraria.objects.create(
            hora_inicio="08:00:00", hora_fin="08:45:00", turno="MANANA"
        )
        self.franja2 = FranjaHoraria.objects.create(
            hora_inicio="08:45:00", hora_fin="09:30:00", turno="MANANA"
        )

        # Authenticate as staff
        self.client.force_login(self.docente)

    def test_assign_schedule_success(self):
        url = reverse("api:asignar_horario")
        data = {
            "curso_id": self.curso.id,
            "franja_id": self.franja.id,
            "dia": "Lunes",
            "duracion": 2,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(BloqueHorario.objects.filter(curso=self.curso).exists())
        bloque = BloqueHorario.objects.get(curso=self.curso)
        self.assertEqual(bloque.duracion_bloques, 2)

    def test_assign_schedule_exceeds_hours(self):
        url = reverse("api:asignar_horario")
        # Try to assign 5 hours (course has 4)
        data = {
            "curso_id": self.curso.id,
            "franja_id": self.franja.id,
            "dia": "Lunes",
            "duracion": 5,
        }
        response = self.client.post(url, data, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
        # Check that no block was created
        self.assertFalse(BloqueHorario.objects.filter(curso=self.curso).exists())

    def test_deassign_schedule(self):
        # Create a block first
        bloque = BloqueHorario.objects.create(
            curso=self.curso, dia="Lunes", franja_inicio=self.franja, duracion_bloques=2
        )

        url = reverse("api:desasignar_horario")
        data = {"bloque_id": bloque.id}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(BloqueHorario.objects.filter(id=bloque.id).exists())

    def test_get_unassigned_courses(self):
        url = reverse("api:get_cursos_no_asignados")
        response = self.client.get(
            url, {"especialidad_id": self.especialidad.id, "semestre_cursado": 1}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]  # success_response wraps in data

        # Check structure
        self.assertIn("cursos_pendientes", data)
        self.assertIn("especialidad", data["cursos_pendientes"])

        # Verify our course is there
        pending = data["cursos_pendientes"]["especialidad"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], self.curso.id)
