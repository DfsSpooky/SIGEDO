from datetime import time, timedelta
import base64
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from core.models import Docente, Curso, AsistenciaDiaria, Asistencia, BloqueHorario, FranjaHoraria, Semestre, Aula

class MobileAttendanceTests(APITestCase):
    def setUp(self):
        # 1. Setup User
        self.docente = Docente.objects.create_user(
            username="docente_test",
            password="password123",
            first_name="Docente",
            last_name="Test",
            id_qr="550e8400-e29b-41d4-a716-446655440000"
        )
        self.user = self.docente

        # 2. Setup JWT
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # 3. Setup Semester
        today = timezone.localtime(timezone.now()).date()
        self.semestre = Semestre.objects.create(
            nombre="2024-I",
            fecha_inicio=today - timedelta(days=30),
            fecha_fin=today + timedelta(days=90),
            estado="ACTIVO"
        )

        # 4. Setup Course
        # Need to create Carrera and Especialidad first as they are required/linked
        from core.models import Carrera
        self.carrera = Carrera.objects.create(nombre="Ingenieria de Sistemas")

        self.curso = Curso.objects.create(
            nombre="Curso Test",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
            # codigo="TEST101", # Field doesn't exist
            # creditos=3        # Field doesn't exist
        )

        # 5. Setup Schedule Block (for Today)
        dia_semana_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
        self.dia_hoy = dia_semana_map.get(today.weekday())

        self.franja = FranjaHoraria.objects.create(
            turno="MANANA",
            hora_inicio=time(8, 0),
            hora_fin=time(9, 30) # 90 min
        )

        # Only create block if it's a weekday (0-4), otherwise tests might fail if run on weekend.
        # But for test consistency, we usually mock the date.
        # For simplicity, we create the block for 'dia_hoy' regardless of what it is,
        # ASSUMING BloqueHorario allows weekend days in 'dia' field even if choices restrict it?
        # BloqueHorario choices are Mon-Fri.
        # If today is Sat/Sun, we might have issues.
        # Let's mock timezone.now() if needed, or just handle Mon-Fri.
        # If test runs on weekend, 'dia_hoy' will be Sabado/Domingo.
        # BloqueHorario choices might fail validation.
        # Let's force today to be Monday if it's weekend, but we can't easily change system time.
        # We can just skip course schedule tests if it's weekend, or assume valid day.
        # Let's rely on validation pass or fail.
        # Ideally, we mock 'timezone.localtime'.

        if today.weekday() < 5:
            self.bloque = BloqueHorario.objects.create(
                curso=self.curso,
                dia=self.dia_hoy,
                franja_inicio=self.franja,
                duracion_bloques=1
            )
        else:
            self.bloque = None # Weekend, no schedule

        # 6. Sample Base64 Image (1x1 transparent png)
        self.photo_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    def test_mobile_status_view(self):
        url = reverse("api:mobile_status")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("teacher", response.data)
        self.assertIn("dailyAttendance", response.data)
        self.assertIn("courses", response.data)
        self.assertEqual(response.data["teacher"]["name"], self.docente.get_full_name())

    def test_mobile_mark_general_entry(self):
        url = reverse("api:mobile_attendance")
        data = {
            "actionType": "general_entry",
            "photoBase64": self.photo_base64
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertTrue(AsistenciaDiaria.objects.filter(docente=self.docente).exists())

    def test_mobile_mark_general_exit_without_entry(self):
        url = reverse("api:mobile_attendance")
        data = {
            "actionType": "general_exit",
            "photoBase64": self.photo_base64
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mobile_mark_general_exit_success(self):
        # Mark entry first
        AsistenciaDiaria.objects.create(docente=self.docente)

        url = reverse("api:mobile_attendance")
        data = {
            "actionType": "general_exit",
            "photoBase64": self.photo_base64
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(AsistenciaDiaria.objects.get(docente=self.docente).hora_salida)

    def test_mobile_mark_course_entry(self):
        url = reverse("api:mobile_attendance")
        data = {
            "actionType": "course_entry",
            "courseId": self.curso.id,
            "photoBase64": self.photo_base64
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Asistencia.objects.filter(docente=self.docente, curso=self.curso).exists())
        asistencia = Asistencia.objects.get(docente=self.docente, curso=self.curso)
        self.assertIsNotNone(asistencia.hora_entrada)

    def test_invalid_photo_format(self):
        url = reverse("api:mobile_attendance")
        data = {
            "actionType": "general_entry",
            "photoBase64": "invalid_base64"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
