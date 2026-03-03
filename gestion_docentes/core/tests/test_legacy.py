import json
import re
from datetime import date, time, timedelta

from django.contrib.auth import authenticate
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from core.backends import DniOrUsernameBackend
from core.models import (
    Anuncio,
    Asistencia,
    AsistenciaDiaria,
    BloqueHorario,
    Carrera,
    ConfiguracionInstitucion,
    Curso,
    DiaEspecial,
    Docente as PersonalDocente,
    Documento,
    Especialidad,
    FranjaHoraria,
    Grupo,
    Justificacion,
    Notificacion,
    Semestre,
    TipoDocumento,
    TipoJustificacion,
)
from core.utils.encryption import decrypt_id, encrypt_id


class CredentialEncryptionTest(TestCase):

    def setUp(self):
        """Set up a test user and a client."""
        self.docente = PersonalDocente.objects.create_user(
            username="testuser",
            password="testpassword123",
            first_name="Test",
            last_name="User",
            dni="12345678",
        )
        # The view `generar_credencial_docente` is decorated with @staff_member_required
        self.staff_user = PersonalDocente.objects.create_user(
            username="staffuser", password="staffpassword123", is_staff=True
        )
        self.client = Client()
        self.client.login(username="staffuser", password="staffpassword123")

    def test_id_encryption_decryption(self):
        """Test that the encryption and decryption functions work correctly."""
        original_id = self.docente.id
        encrypted_id = encrypt_id(original_id)
        self.assertIsNotNone(encrypted_id)
        self.assertIsInstance(encrypted_id, str)

        decrypted_id = decrypt_id(encrypted_id)
        self.assertEqual(original_id, decrypted_id)

    def test_invalid_id_decryption(self):
        """Test that decrypting a bogus string returns None."""
        bogus_encrypted_string = "thisisnotarealencryptedstring"
        decrypted_id = decrypt_id(bogus_encrypted_string)
        self.assertIsNone(decrypted_id)

    def test_generar_credencial_view_with_valid_encrypted_id(self):
        """
        Test that the view returns a 200 OK response for a valid encrypted ID.
        """
        encrypted_id = encrypt_id(self.docente.id)
        url = reverse("generar_credencial", args=[encrypted_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.docente.first_name)

    def test_generar_credencial_view_with_invalid_encrypted_id(self):
        """
        Test that the view returns a 404 Not Found for an invalid encrypted ID.
        """
        bogus_encrypted_id = "thisisbogus"
        url = reverse("generar_credencial", args=[bogus_encrypted_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_credential_list_view_uses_encrypted_url(self):
        """
        Test that the list view contains a valid, decryptable encrypted URL.
        """
        list_url = reverse("lista_credenciales")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

        # Instead of matching the exact encrypted string, we find the link,
        # extract the encrypted part, and try to decrypt it.
        response_content = response.content.decode("utf-8")

        # Regex to find the URL for the specific docente we created
        # It looks for the link within the table row for our test user by finding their DNI
        pattern = r'12345678.*?<a href="\/credenciales\/(.*?)\/"'
        match = re.search(pattern, response_content, re.DOTALL)

        self.assertIsNotNone(
            match,
            "Could not find the credential link for the test user in the response.",
        )

        encrypted_id_from_html = match.group(1)
        decrypted_id = decrypt_id(encrypted_id_from_html)

        self.assertEqual(
            decrypted_id,
            self.docente.id,
            "The encrypted ID in the link does not decrypt to the correct docente ID.",
        )


class AnuncioTest(TestCase):

    def setUp(self):
        """Set up users for announcement tests."""
        self.admin_user = PersonalDocente.objects.create_superuser(
            username="superadmin2", password="superpassword123", dni="77777777"
        )
        self.teacher = PersonalDocente.objects.create_user(
            username="teacheruser2", password="teacherpassword123", dni="66666666"
        )
        self.client = Client()

    def test_announcement_workflow(self):
        """Test that an admin can create an announcement and a teacher can see it."""
        # 1. Admin creates an announcement
        self.client.login(username="superadmin2", password="superpassword123")
        Anuncio.objects.create(
            autor=self.admin_user,
            titulo="Anuncio de Prueba",
            contenido="Este es el contenido del anuncio.",
        )
        self.assertEqual(Anuncio.objects.count(), 1)

        # 2. Teacher logs in and views the announcement
        self.client.login(username="teacheruser2", password="teacherpassword123")
        response = self.client.get(reverse("ver_anuncios"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anuncio de Prueba")
        self.assertContains(response, "Este es el contenido del anuncio.")


class NotificationTest(TestCase):

    def setUp(self):
        """Set up users and a document for notification tests."""
        self.admin_user = PersonalDocente.objects.create_superuser(
            username="superadmin", password="superpassword123", dni="99999999"
        )
        self.teacher = PersonalDocente.objects.create_user(
            username="teacheruser", password="teacherpassword123", dni="88888888"
        )
        self.tipo_doc = TipoDocumento.objects.create(nombre="Test Type")
        self.document = Documento.objects.create(
            titulo="Test Document", docente=self.teacher, tipo_documento=self.tipo_doc
        )
        self.client = Client()

    def test_notification_creation_on_status_change(self):
        """Test that a notification is created when a document's status changes."""
        # Check that there are no notifications initially
        self.assertEqual(Notificacion.objects.count(), 0)

        # Change the document status and save it
        self.document.estado = "APROBADO"
        self.document.save()

        # Check that one notification has been created
        self.assertEqual(Notificacion.objects.count(), 1)
        notification = Notificacion.objects.first()
        self.assertEqual(notification.destinatario, self.teacher)
        self.assertIn("aprobado", notification.mensaje)

        # Test the 'OBSERVADO' case
        self.document.estado = "OBSERVADO"
        self.document.save()
        self.assertEqual(Notificacion.objects.count(), 2)
        notification = Notificacion.objects.latest("fecha_creacion")
        self.assertEqual(notification.destinatario, self.teacher)
        self.assertIn("observaciones", notification.mensaje)

    def test_mark_as_read_on_visit(self):
        """Test that visiting the notifications page marks them as read."""
        # Create a notification manually for the teacher
        Notificacion.objects.create(
            destinatario=self.teacher, mensaje="Test notification"
        )

        # Log in as the teacher
        self.client.login(username="teacheruser", password="teacherpassword123")

        # Visit the notifications page
        notifications_url = reverse("ver_notificaciones")
        response = self.client.get(notifications_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test notification")

        # Check that the notification is now marked as read
        self.assertEqual(
            Notificacion.objects.filter(destinatario=self.teacher, leido=True).count(),
            1,
        )


class ReporteAsistenciaTest(TestCase):

    def setUp(self):
        """Set up a staff user and a regular user for testing."""
        self.staff_user = PersonalDocente.objects.create_superuser(
            username="staffuser",
            password="staffpassword123",
            dni="87654321",
            first_name="Staff",
            last_name="User",
        )
        self.docente = PersonalDocente.objects.create_user(
            username="testdocente",
            password="testpassword123",
            dni="12345678",
            first_name="Test",
            last_name="Docente",
        )
        self.client = Client()
        self.client.login(username="staffuser", password="staffpassword123")
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Software")

    def test_get_detalle_docente_api(self):
        """
        Test the API endpoint that retrieves detailed attendance info for the modal.
        """
        # URL for the detail API
        url = reverse("api:detalle_asistencia_docente_ajax", args=[self.docente.id])

        # Make the request
        response = self.client.get(url)

        # Check that the response is successful and is JSON
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        # Parse the JSON and check the new standardized structure
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("data", data)

        response_data = data["data"]
        self.assertIn("docente", response_data)
        self.assertIn("asistencias_cursos", response_data)
        self.assertEqual(response_data["docente"]["nombre_completo"], "Test Docente")
        self.assertEqual(response_data["docente"]["dni"], "12345678")

    def test_reporte_asistencia_logic(self):
        """
        Test the core logic of the attendance report for Presente, Tardanza, and Falta.
        """
        # 1. Setup
        today = date.today()
        # Ensure today is a Monday for predictability
        today = today - timedelta(days=today.weekday())

        Semestre.objects.create(
            nombre="Test Semestre",
            fecha_inicio=today - timedelta(days=30),
            fecha_fin=today + timedelta(days=30),
            estado="ACTIVO",
        )
        config = ConfiguracionInstitucion.load()
        config.tiempo_limite_tardanza = 15
        config.save()

        curso_manana = Curso.objects.create(
            docente=self.docente,
            nombre="Curso de Mañana",
            semestre=Semestre.objects.first(),
            carrera=self.carrera,
        )
        franja = FranjaHoraria.objects.create(
            turno="MANANA", hora_inicio=time(9, 0), hora_fin=time(10, 50)
        )
        BloqueHorario.objects.create(
            curso=curso_manana, dia="Lunes", franja_inicio=franja, duracion_bloques=2
        )

        # 2. Test "Falta" (Absent)
        url = reverse("reporte_asistencia") + f"?fecha_inicio={today}&fecha_fin={today}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context["page_obj"].object_list
        # Find the record for our specific teacher and day
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.docente and r["fecha"] == today
            ),
            None,
        )
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report["estado"], "Falta")

        # 3. Test "Presente" (Present)
        Asistencia.objects.create(
            docente=self.docente,
            curso=curso_manana,
            fecha=today,
            hora_entrada=make_aware(
                timezone.datetime.combine(today, time(9, 5))
            ),  # On time
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context["page_obj"].object_list
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.docente and r["fecha"] == today
            ),
            None,
        )
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report["estado"], "Presente")

        # 4. Test "Tardanza" (Late)
        Asistencia.objects.all().delete()  # Clear previous attendance
        Asistencia.objects.create(
            docente=self.docente,
            curso=curso_manana,
            fecha=today,
            hora_entrada=make_aware(
                timezone.datetime.combine(today, time(9, 20))
            ),  # 20 mins late
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context["page_obj"].object_list
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.docente and r["fecha"] == today
            ),
            None,
        )
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report["estado"], "Tardanza")

        # 5. Test "No Requerido"
        # Check for Tuesday, when there are no classes scheduled
        tuesday = today + timedelta(days=1)
        url = (
            reverse("reporte_asistencia")
            + f"?fecha_inicio={tuesday}&fecha_fin={tuesday}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context["page_obj"].object_list
        # By default (filter='todos'), the "No Requerido" status should be present.
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.docente and r["fecha"] == tuesday
            ),
            None,
        )
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report["estado"], "No Requerido")

        # Now check with a different filter, it should not be present
        url_presente = url + "&estado=presente"
        response = self.client.get(url_presente)
        report_data = response.context["page_obj"].object_list
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.docente and r["fecha"] == tuesday
            ),
            None,
        )
        self.assertIsNone(docente_report)


class JustificacionTest(TestCase):

    def setUp(self):
        """Set up users and objects for justification tests."""
        self.staff_user = PersonalDocente.objects.create_superuser(
            username="staffuser_just", password="staffpassword123", dni="11112222"
        )
        self.teacher = PersonalDocente.objects.create_user(
            username="teacher_just",
            password="teacherpassword123",
            dni="33334444",
            first_name="Justo",
            last_name="Profesor",
        )
        self.tipo_justificacion = TipoJustificacion.objects.create(
            nombre="Licencia Médica"
        )
        self.client = Client()

    def test_justificacion_model_creation(self):
        """Test that a Justificacion instance can be created successfully."""
        today = date.today()
        justificacion = Justificacion.objects.create(
            docente=self.teacher,
            tipo=self.tipo_justificacion,
            fecha_inicio=today,
            fecha_fin=today + timedelta(days=1),
            motivo="Cita médica.",
            estado="PENDIENTE",
        )
        self.assertEqual(Justificacion.objects.count(), 1)
        self.assertEqual(justificacion.docente.first_name, "Justo")
        self.assertEqual(justificacion.get_estado_display(), "Pendiente")

    def test_solicitar_justificacion_view_for_teacher(self):
        """Test that a teacher can access and submit the justification form."""
        self.client.login(username="teacher_just", password="teacherpassword123")
        url = reverse("solicitar_justificacion")

        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nueva Solicitud de Justificación")

        # Test POST request
        today = date.today()
        post_data = {
            "tipo": self.tipo_justificacion.id,
            "fecha_inicio": today.strftime("%Y-%m-%d"),
            "fecha_fin": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            "motivo": "Congreso académico",
        }
        response = self.client.post(url, post_data)

        # Should redirect to the list view after successful submission
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("lista_justificaciones"))
        self.assertEqual(Justificacion.objects.count(), 1)
        self.assertEqual(Justificacion.objects.first().motivo, "Congreso académico")

    def test_lista_justificaciones_view_for_staff(self):
        """Test that a staff member can view and approve/reject justifications."""
        self.client.login(username="staffuser_just", password="staffpassword123")

        justificacion = Justificacion.objects.create(
            docente=self.teacher,
            tipo=self.tipo_justificacion,
            fecha_inicio=date.today(),
            fecha_fin=date.today(),
            motivo="Test motivo",
            estado="PENDIENTE",
        )

        url = reverse("lista_justificaciones")

        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestionar Justificaciones")
        self.assertContains(response, "Justo Profesor")

        # Test POST request to approve
        response = self.client.post(
            url, {"justificacion_id": justificacion.id, "accion": "aprobar"}
        )
        self.assertEqual(response.status_code, 302)
        justificacion.refresh_from_db()
        self.assertEqual(justificacion.estado, "APROBADO")
        self.assertEqual(justificacion.revisado_por, self.staff_user)

        # Test POST request to reject
        justificacion.estado = "PENDIENTE"
        justificacion.save()
        response = self.client.post(
            url, {"justificacion_id": justificacion.id, "accion": "rechazar"}
        )
        self.assertEqual(response.status_code, 302)
        justificacion.refresh_from_db()
        self.assertEqual(justificacion.estado, "RECHAZADO")

    def test_reporte_asistencia_with_justificacion(self):
        """
        Test that an approved justification correctly changes the status from 'Falta' to 'Justificado'.
        """
        self.client.login(username="staffuser_just", password="staffpassword123")
        today = date.today()
        # Ensure today is a Monday for predictability
        today = today - timedelta(days=today.weekday())

        Semestre.objects.create(
            nombre="Test Semestre Just",
            fecha_inicio=today - timedelta(days=30),
            fecha_fin=today + timedelta(days=30),
            estado="ACTIVO",
        )
        carrera = Carrera.objects.create(nombre="Ingeniería de Justificaciones")
        curso = Curso.objects.create(
            docente=self.teacher,
            nombre="Curso con Falta",
            semestre=Semestre.objects.first(),
            carrera=carrera,
        )
        franja = FranjaHoraria.objects.create(
            turno="TARDE", hora_inicio=time(14, 0), hora_fin=time(15, 50)
        )
        BloqueHorario.objects.create(
            curso=curso, dia="Lunes", franja_inicio=franja, duracion_bloques=2
        )

        # 1. First, confirm the status is 'Falta' without justification
        url = reverse("reporte_asistencia") + f"?fecha_inicio={today}&fecha_fin={today}"
        response = self.client.get(url)
        report_data = response.context["page_obj"].object_list
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.teacher and r["fecha"] == today
            ),
            None,
        )
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report["estado"], "Falta")

        # 2. Now, add an approved justification for that day
        Justificacion.objects.create(
            docente=self.teacher,
            tipo=self.tipo_justificacion,
            fecha_inicio=today,
            fecha_fin=today,
            motivo="Ausencia justificada",
            estado="APROBADO",
            revisado_por=self.staff_user,
        )

        # 3. Re-fetch the report and check that the status is now 'Justificado'
        response = self.client.get(url)
        report_data = response.context["page_obj"].object_list
        docente_report = next(
            (
                r
                for r in report_data
                if r["docente"] == self.teacher and r["fecha"] == today
            ),
            None,
        )
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report["estado"], "Justificado")


from unittest.mock import AsyncMock, MagicMock, patch


class RfidAsistenciaTest(TestCase):

    def setUp(self):
        """Set up a test user with an RFID UID and a client."""
        self.rfid_uid = "0A:1B:2C:3D"
        self.docente = PersonalDocente.objects.create(
            username="rfiduser",
            password="rfidpassword",
            dni="87654321",
            first_name="RFID",
            last_name="User",
            rfid_uid=self.rfid_uid,
        )
        self.client = Client()
        self.url = reverse("api:asistencia_rfid")

    @patch("django.utils.timezone.now")
    def test_registrar_asistencia_rfid_success(self, mock_now):
        """Test successful retrieval of teacher info via RFID on a weekday."""
        # Mock 'now' to be a weekday
        mock_now.return_value = make_aware(
            timezone.datetime(2023, 10, 26, 10, 0, 0)
        )  # A Thursday

        self.assertEqual(AsistenciaDiaria.objects.count(), 0)
        payload = json.dumps({"uid": self.rfid_uid})
        response = self.client.post(
            self.url, data=payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("teacher", response_data)
        self.assertEqual(response_data["teacher"]["name"], "RFID User")
        # Attendance should NOT be created automatically anymore
        self.assertEqual(AsistenciaDiaria.objects.count(), 0)

    @patch("django.utils.timezone.now")
    def test_registrar_asistencia_rfid_not_found(self, mock_now):
        """Test registration with an unregistered RFID UID."""
        # Mock 'now' to be a weekday to bypass the weekend check
        mock_now.return_value = make_aware(
            timezone.datetime(2023, 10, 26, 10, 0, 0)
        )  # A Thursday

        payload = json.dumps({"uid": "XX:XX:XX:XX"})
        response = self.client.post(
            self.url, data=payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("no reconocida", response.json()["message"])
        self.assertEqual(AsistenciaDiaria.objects.count(), 0)

    def test_registrar_asistencia_rfid_bad_request_no_uid(self):
        """Test registration with missing UID in payload."""
        payload = json.dumps({"other_key": "some_value"})
        response = self.client.post(
            self.url, data=payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("Datos inválidos", response.json()["message"])

    @patch("django.utils.timezone.now")
    def test_registrar_asistencia_rfid_weekend(self, mock_now):
        """Test that retrieval is allowed on weekends (weekend block removed)."""
        # Mock 'now' to be a Saturday
        mock_now.return_value = make_aware(
            timezone.datetime(2023, 10, 28, 10, 0, 0)
        )  # A Saturday

        payload = json.dumps({"uid": self.rfid_uid})
        response = self.client.post(
            self.url, data=payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        # Should now be success, not weekend_off
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(AsistenciaDiaria.objects.count(), 0)


from datetime import datetime
from io import StringIO

from django.core.management import call_command


class AutoCheckoutTest(TestCase):

    def setUp(self):
        self.docente = PersonalDocente.objects.create_user(
            username="checkout_user", dni="87654321"
        )
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Checkout")
        self.semestre = Semestre.objects.create(
            nombre="Test Semestre Checkout",
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin=date.today() + timedelta(days=30),
            estado="ACTIVO",
        )

        franja_pasada = FranjaHoraria.objects.create(
            turno="MANANA", hora_inicio=time(8, 0), hora_fin=time(10, 0)
        )
        franja_futura = FranjaHoraria.objects.create(
            turno="TARDE", hora_inicio=time(18, 0), hora_fin=time(20, 0)
        )

        self.curso_pasado = Curso.objects.create(
            docente=self.docente,
            nombre="Curso Pasado",
            semestre=self.semestre,
            carrera=self.carrera,
        )
        BloqueHorario.objects.create(
            curso=self.curso_pasado,
            dia="Lunes",
            franja_inicio=franja_pasada,
            duracion_bloques=2,
        )

        self.curso_futuro = Curso.objects.create(
            docente=self.docente,
            nombre="Curso Futuro",
            semestre=self.semestre,
            carrera=self.carrera,
        )
        BloqueHorario.objects.create(
            curso=self.curso_futuro,
            dia="Lunes",
            franja_inicio=franja_futura,
            duracion_bloques=2,
        )

        # Create an attendance record for a course that has already ended today
        # but has no checkout time.
        today = date.today()
        # Ensure the date is a Monday to match the created BloqueHorario
        last_monday = today - timedelta(days=today.weekday())

        self.asistencia_abierta = Asistencia.objects.create(
            docente=self.docente,
            curso=self.curso_pasado,
            fecha=last_monday,
            hora_entrada=timezone.make_aware(datetime.combine(last_monday, time(8, 5))),
        )

        # Create an attendance record for a course that has not yet ended today.
        self.asistencia_futura = Asistencia.objects.create(
            docente=self.docente,
            curso=self.curso_futuro,
            fecha=today,  # This can remain today as it's for a future course check
            hora_entrada=timezone.now(),
        )

    @patch("django.utils.timezone.now")
    def test_auto_checkout_command(self, mock_now):
        """
        Test that the auto_checkout_courses command correctly closes open attendances
        for courses that have already ended.
        """
        # Mock 'now' to be a time after the past course has ended, but before the future one.
        mock_now.return_value = timezone.make_aware(
            datetime.combine(date.today(), time(12, 0))
        )

        out = StringIO()
        call_command("auto_checkout_courses", stdout=out)

        self.asistencia_abierta.refresh_from_db()
        self.asistencia_futura.refresh_from_db()

        # The open attendance for the past course should now be closed.
        self.assertIsNotNone(self.asistencia_abierta.hora_salida)

        # The exit time should be the scheduled end time of the course.
        bloque_pasado = BloqueHorario.objects.get(curso=self.curso_pasado)
        expected_checkout_time = timezone.make_aware(
            datetime.combine(self.asistencia_abierta.fecha, bloque_pasado.horario_fin)
        )
        self.assertEqual(self.asistencia_abierta.hora_salida, expected_checkout_time)

        # The open attendance for the future course should remain open.
        self.assertIsNone(self.asistencia_futura.hora_salida)

        self.assertIn("1 attendances were closed", out.getvalue())


class NotificationCreationTest(TestCase):

    def setUp(self):
        """Set up a test user and a client."""
        self.docente = PersonalDocente.objects.create_user(
            username="teacher_for_notification",
            password="testpassword123",
            dni="11223344",
        )
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Notificaciones")
        self.semestre = Semestre.objects.create(
            nombre="Test Semestre Notificaciones",
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin=date.today() + timedelta(days=30),
            estado="ACTIVO",
        )
        self.curso = Curso.objects.create(
            nombre="Curso de Prueba para Notificaciones",
            carrera=self.carrera,
            semestre=self.semestre,
        )

    @patch("core.signals.get_channel_layer")
    def test_notification_on_course_assignment(self, mock_get_channel_layer):
        """
        Test that a notification is created and broadcasted when a course is assigned to a teacher.
        """
        mock_channel_layer = mock_get_channel_layer.return_value
        mock_channel_layer.group_send = AsyncMock()

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.curso.docente = self.docente
            self.curso.save()

        self.assertTrue(Notificacion.objects.filter(destinatario=self.docente).exists())
        self.assertEqual(len(callbacks), 1)
        mock_channel_layer.group_send.assert_called_once()

    @patch("core.signals.get_channel_layer")
    def test_notification_on_announcement(self, mock_get_channel_layer):
        """
        Test that a notification is created for all users when a new announcement is made.
        """
        docente2 = PersonalDocente.objects.create_user(
            username="teacher2_for_notification",
            password="testpassword123",
            dni="55667788",
        )
        mock_channel_layer = mock_get_channel_layer.return_value
        mock_channel_layer.group_send = AsyncMock()

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            Anuncio.objects.create(
                titulo="Anuncio de Prueba",
                contenido="Este es un anuncio de prueba.",
                autor=self.docente,
            )

        self.assertTrue(Notificacion.objects.filter(destinatario=self.docente).exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=docente2).exists())
        self.assertEqual(len(callbacks), 2)
        self.assertEqual(mock_channel_layer.group_send.call_count, 2)

        # Verify that group_send was called for each user's specific group
        expected_groups = {
            f"notifications_{self.docente.id}",
            f"notifications_{docente2.id}",
        }
        actual_groups = {
            call[0][0] for call in mock_channel_layer.group_send.call_args_list
        }
        self.assertEqual(expected_groups, actual_groups)


class DniOrUsernameBackendTest(TestCase):

    def setUp(self):
        """Set up a test user for authentication tests."""
        self.password = "testpassword123"
        self.username = "auth_test_user"
        self.dni = "12312312"
        self.user = PersonalDocente.objects.create_user(
            username=self.username, password=self.password, dni=self.dni
        )

    def test_authenticate_with_username_success(self):
        """Test successful authentication using the username."""
        user = authenticate(username=self.username, password=self.password)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.username)

    def test_authenticate_with_dni_success(self):
        """Test successful authentication using the DNI."""
        user = authenticate(username=self.dni, password=self.password)
        self.assertIsNotNone(user)
        self.assertEqual(user.dni, self.dni)
        self.assertEqual(user.username, self.username)

    def test_authenticate_with_case_insensitive_username(self):
        """Test successful authentication with a case-insensitive username."""
        user = authenticate(username=self.username.upper(), password=self.password)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.username)

    def test_authenticate_with_wrong_password(self):
        """Test that authentication fails with an incorrect password."""
        user = authenticate(username=self.username, password="wrongpassword")
        self.assertIsNone(user)

    def test_authenticate_with_nonexistent_user(self):
        """Test that authentication fails for a user that does not exist."""
        user = authenticate(username="nonexistentuser", password="anypassword")
        self.assertIsNone(user)


class HorarioFlexibleTest(TestCase):
    def setUp(self):
        """Set up a test environment for flexible scheduling."""
        self.client = Client()
        self.admin_user = PersonalDocente.objects.create_superuser(
            username="admin_horarios", password="password", dni="11111111"
        )
        self.client.login(username="admin_horarios", password="password")

        self.docente = PersonalDocente.objects.create_user(
            username="profesor_flexible", password="password", dni="22222222"
        )
        self.semestre = Semestre.objects.create(
            nombre="Semestre de Prueba Flex",
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin=date.today() + timedelta(days=30),
            estado="ACTIVO",
        )
        self.carrera = Carrera.objects.create(nombre="Ingeniería Flexible")
        self.grupo = Grupo.objects.create(nombre="Grupo Test")
        self.especialidad = Especialidad.objects.create(
            nombre="Especialidad Test", grupo=self.grupo
        )

        # Crear franjas horarias para mañana y tarde
        for i in range(8, 13):  # Mañana
            FranjaHoraria.objects.create(
                turno="MANANA", hora_inicio=time(i, 0), hora_fin=time(i, 50)
            )
        for i in range(14, 19):  # Tarde
            FranjaHoraria.objects.create(
                turno="TARDE", hora_inicio=time(i, 0), hora_fin=time(i, 50)
            )

        self.url_generar = reverse("api:generar_horario_automatico")
        self.url_asignar = reverse("api:asignar_horario")
        self.url_desasignar = reverse("api:desasignar_horario")

    def test_generar_horario_distribuido(self):
        """
        Test that the automatic generator can create multiple blocks for a single course
        to meet its weekly hours requirement.
        """
        # Crear un curso que requiere 6 horas semanales
        curso = Curso.objects.create(
            nombre="Cálculo Avanzado",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
            semestre_cursado=1,
            horas_academicas_semanales=6,
        )
        curso.especialidades.add(self.especialidad)

        self.assertEqual(BloqueHorario.objects.count(), 0)

        # Ejecutar el generador automático
        response = self.client.post(self.url_generar)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        # Verificar que se crearon bloques para el curso
        bloques = BloqueHorario.objects.filter(curso=curso)
        self.assertTrue(bloques.exists())

        # Verificar que la suma de las duraciones de los bloques es igual a las horas semanales
        total_horas_asignadas = sum(b.duracion_bloques for b in bloques)
        self.assertEqual(total_horas_asignadas, curso.horas_academicas_semanales)

        # Verificar que la distribución es razonable (p.ej. 3 bloques de 2h, 2 de 3h, etc.)
        # La lógica actual intenta bloques de 3, 2, 1. Para 6h, debería ser 3+3 o 3+2+1 o 2+2+2
        duraciones = [b.duracion_bloques for b in bloques]
        self.assertIn(sorted(duraciones), [[3, 3], [1, 2, 3], [2, 2, 2]])

    def test_asignar_y_desasignar_bloque_manual(self):
        """
        Test manual assignment and deassignment of a single schedule block.
        """
        curso = Curso.objects.create(
            nombre="Física Cuántica",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
            semestre_cursado=1,
            horas_academicas_semanales=4,
        )
        curso.especialidades.add(self.especialidad)
        franja_inicio = FranjaHoraria.objects.filter(turno="MANANA").first()

        # 1. Asignar un bloque de 2 horas
        payload_asignar = {
            "curso_id": curso.id,
            "dia": "Lunes",
            "franja_id": franja_inicio.id,
            "duracion": 2,
        }
        response = self.client.post(
            self.url_asignar,
            json.dumps(payload_asignar),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        self.assertEqual(BloqueHorario.objects.count(), 1)
        bloque = BloqueHorario.objects.first()
        self.assertEqual(bloque.curso, curso)
        self.assertEqual(bloque.duracion_bloques, 2)

        # 2. Desasignar el bloque creado
        payload_desasignar = {"bloque_id": bloque.id}
        response = self.client.post(
            self.url_desasignar,
            json.dumps(payload_desasignar),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        self.assertEqual(BloqueHorario.objects.count(), 0)

    def test_mover_bloque_existente(self):
        """Test that an existing block can be moved to a new day and slot."""
        curso = Curso.objects.create(
            nombre="Curso Movible",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
            horas_academicas_semanales=4,
        )
        franja1 = FranjaHoraria.objects.get(hora_inicio=time(9, 0))
        franja2 = FranjaHoraria.objects.get(hora_inicio=time(14, 0))

        bloque = BloqueHorario.objects.create(
            curso=curso, dia="Lunes", franja_inicio=franja1, duracion_bloques=2
        )
        self.assertEqual(bloque.dia, "Lunes")

        # Mover el bloque al martes
        url = reverse("api:mover_bloque")
        payload = {"bloque_id": bloque.id, "dia": "Martes", "franja_id": franja2.id}
        response = self.client.post(
            url, json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        bloque.refresh_from_db()
        self.assertEqual(bloque.dia, "Martes")
        self.assertEqual(bloque.franja_inicio, franja2)

    def test_ajustar_duracion_bloque(self):
        """Test that a block's duration can be increased and decreased."""
        curso = Curso.objects.create(
            nombre="Curso Ajustable",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
            horas_academicas_semanales=5,
        )
        franja = FranjaHoraria.objects.get(hora_inicio=time(10, 0))
        bloque = BloqueHorario.objects.create(
            curso=curso, dia="Miércoles", franja_inicio=franja, duracion_bloques=2
        )

        url = reverse("api:ajustar_duracion")

        # Aumentar duración
        payload_increase = {"bloque_id": bloque.id, "accion": "increase"}
        response_increase = self.client.post(
            url, json.dumps(payload_increase), content_type="application/json"
        )
        self.assertEqual(response_increase.status_code, 200)
        bloque.refresh_from_db()
        self.assertEqual(bloque.duracion_bloques, 3)

        # Disminuir duración
        payload_decrease = {"bloque_id": bloque.id, "accion": "decrease"}
        response_decrease = self.client.post(
            url, json.dumps(payload_decrease), content_type="application/json"
        )
        self.assertEqual(response_decrease.status_code, 200)
        bloque.refresh_from_db()
        self.assertEqual(bloque.duracion_bloques, 2)

        # Probar límite inferior (no puede ser menos de 1)
        self.client.post(
            url, json.dumps(payload_decrease), content_type="application/json"
        )  # a 1
        response_limit = self.client.post(
            url, json.dumps(payload_decrease), content_type="application/json"
        )  # intentar bajar a 0
        self.assertEqual(response_limit.status_code, 400)
        bloque.refresh_from_db()
        self.assertEqual(bloque.duracion_bloques, 1)

    def test_asignar_bloque_excediendo_horas(self):
        """
        Test that the API prevents assigning a block that would exceed the course's total weekly hours.
        """
        curso = Curso.objects.create(
            nombre="Termodinámica",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
            semestre_cursado=1,
            horas_academicas_semanales=2,  # Solo 2 horas permitidas
        )
        curso.especialidades.add(self.especialidad)
        franja_inicio = FranjaHoraria.objects.filter(turno="MANANA").first()

        # Intentar asignar un bloque de 3 horas (más de las 2 permitidas)
        payload = {
            "curso_id": curso.id,
            "dia": "Martes",
            "franja_id": franja_inicio.id,
            "duracion": 3,
        }
        response = self.client.post(
            self.url_asignar, json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)  # Bad Request
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("excede las horas semanales", response.json()["message"])

        self.assertEqual(BloqueHorario.objects.count(), 0)


from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from core.consumers import CalendarConsumer


class CalendarRealtimeTest(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.docente = PersonalDocente.objects.create_user(
            username="calendar_user", password="password", dni="98765432"
        )
        self.semestre = Semestre.objects.create(
            nombre="Semestre Calendario",
            fecha_inicio=date(2023, 1, 1),
            fecha_fin=date(2023, 6, 30),
            estado="ACTIVO",
        )
        self.carrera = Carrera.objects.create(nombre="Ingenieria de Calendarios")
        self.curso = Curso.objects.create(
            nombre="Curso de Calendario",
            docente=self.docente,
            semestre=self.semestre,
            carrera=self.carrera,
        )
        self.franja = FranjaHoraria.objects.create(
            turno="MANANA", hora_inicio=time(8, 0), hora_fin=time(8, 50)
        )
        DiaEspecial.objects.create(
            fecha=date(2023, 5, 1),
            motivo="Feriado",
            tipo="FERIADO",
            semestre=self.semestre,
        )
        self.api_url = reverse("api:horario_docente")

    def test_api_horario_docente_authenticated(self):
        """Test that an authenticated user can get their schedule data."""
        self.client.login(username="calendar_user", password="password")
        bloque = BloqueHorario.objects.create(
            curso=self.curso, dia="Lunes", franja_inicio=self.franja, duracion_bloques=2
        )
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)  # 1 bloque + 1 dia especial

        # Check recurring event
        bloque_event = next(
            item for item in data if item["id"] == f"bloque_{bloque.id}"
        )
        self.assertEqual(bloque_event["title"], "Curso de Calendario")
        self.assertEqual(bloque_event["daysOfWeek"], [1])  # Monday
        self.assertEqual(bloque_event["startRecur"], "2023-01-01")

        # Check special day event
        especial_event = next(item for item in data if "especial" in item["id"])
        self.assertEqual(especial_event["title"], "Feriado")
        self.assertEqual(especial_event["display"], "background")

    def test_api_horario_docente_unauthenticated(self):
        """Test that an unauthenticated user cannot access the endpoint."""
        response = self.client.get(self.api_url)
        # JWT returns 401 for unauthenticated, DRF standard is sometimes 403. Accepting both.
        self.assertIn(response.status_code, [401, 403])

    async def test_calendar_consumer_auth(self):
        """Test that the CalendarConsumer handles authenticated connections."""
        communicator = WebsocketCommunicator(
            CalendarConsumer.as_asgi(), "/ws/calendar/"
        )
        communicator.scope["user"] = self.docente
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_calendar_consumer_unauth(self):
        """Test that the CalendarConsumer closes connections for unauthenticated users."""
        from django.contrib.auth.models import AnonymousUser

        communicator = WebsocketCommunicator(
            CalendarConsumer.as_asgi(), "/ws/calendar/"
        )
        communicator.scope["user"] = AnonymousUser()
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    @patch("core.signals.broadcast_horario_update")
    def test_post_save_signal_sends_update(self, mock_broadcast):
        """Test that saving a BloqueHorario triggers the broadcast function."""
        bloque = BloqueHorario.objects.create(
            curso=self.curso, dia="Lunes", franja_inicio=self.franja, duracion_bloques=2
        )
        mock_broadcast.assert_called_once_with(self.docente.id)

        bloque.save()
        self.assertEqual(mock_broadcast.call_count, 2)

    @patch("core.signals.broadcast_horario_update")
    def test_post_delete_signal_sends_update(self, mock_broadcast):
        """Test that deleting a BloqueHorario triggers the broadcast function."""
        bloque = BloqueHorario.objects.create(
            curso=self.curso, dia="Lunes", franja_inicio=self.franja, duracion_bloques=2
        )
        mock_broadcast.reset_mock()

        bloque.delete()
        mock_broadcast.assert_called_once_with(self.docente.id)
