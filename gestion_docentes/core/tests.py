from django.test import TestCase, Client
from django.urls import reverse
from .models import PersonalDocente, Notificacion, TipoDocumento, Documento, Anuncio, Semestre, ConfiguracionInstitucion, Curso, Asistencia, AsistenciaDiaria, Carrera, Justificacion, TipoJustificacion
from .utils.encryption import encrypt_id, decrypt_id
import re
from django.utils import timezone
from datetime import time
from django.utils.timezone import make_aware
import json
from datetime import date, timedelta

class CredentialEncryptionTest(TestCase):

    def setUp(self):
        """Set up a test user and a client."""
        self.docente = PersonalDocente.objects.create_user(
            username='testuser',
            password='testpassword123',
            first_name='Test',
            last_name='User',
            dni='12345678'
        )
        # The view `generar_credencial_docente` is decorated with @staff_member_required
        self.staff_user = PersonalDocente.objects.create_user(
            username='staffuser',
            password='staffpassword123',
            is_staff=True
        )
        self.client = Client()
        self.client.login(username='staffuser', password='staffpassword123')

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
        url = reverse('generar_credencial', args=[encrypted_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.docente.first_name)

    def test_generar_credencial_view_with_invalid_encrypted_id(self):
        """
        Test that the view returns a 404 Not Found for an invalid encrypted ID.
        """
        bogus_encrypted_id = "thisisbogus"
        url = reverse('generar_credencial', args=[bogus_encrypted_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_credential_list_view_uses_encrypted_url(self):
        """
        Test that the list view contains a valid, decryptable encrypted URL.
        """
        list_url = reverse('lista_credenciales')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

        # Instead of matching the exact encrypted string, we find the link,
        # extract the encrypted part, and try to decrypt it.
        response_content = response.content.decode('utf-8')

        # Regex to find the URL for the specific docente we created
        # It looks for the link within the div for our test user
        pattern = r'<h2 class="card-title text-lg">Test User<\/h2>.*?<a href="\/credenciales\/(.*?)\/"'
        match = re.search(pattern, response_content, re.DOTALL)

        self.assertIsNotNone(match, "Could not find the credential link for the test user in the response.")

        encrypted_id_from_html = match.group(1)
        decrypted_id = decrypt_id(encrypted_id_from_html)

        self.assertEqual(decrypted_id, self.docente.id, "The encrypted ID in the link does not decrypt to the correct docente ID.")




class AnuncioTest(TestCase):

    def setUp(self):
        """Set up users for announcement tests."""
        self.admin_user = PersonalDocente.objects.create_superuser(
            username='superadmin2',
            password='superpassword123',
            dni='77777777'
        )
        self.teacher = PersonalDocente.objects.create_user(
            username='teacheruser2',
            password='teacherpassword123',
            dni='66666666'
        )
        self.client = Client()

    def test_announcement_workflow(self):
        """Test that an admin can create an announcement and a teacher can see it."""
        # 1. Admin creates an announcement
        self.client.login(username='superadmin2', password='superpassword123')
        Anuncio.objects.create(
            autor=self.admin_user,
            titulo="Anuncio de Prueba",
            contenido="Este es el contenido del anuncio."
        )
        self.assertEqual(Anuncio.objects.count(), 1)

        # 2. Teacher logs in and views the announcement
        self.client.login(username='teacheruser2', password='teacherpassword123')
        response = self.client.get(reverse('ver_anuncios'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anuncio de Prueba")
        self.assertContains(response, "Este es el contenido del anuncio.")


class NotificationTest(TestCase):

    def setUp(self):
        """Set up users and a document for notification tests."""
        self.admin_user = PersonalDocente.objects.create_superuser(
            username='superadmin',
            password='superpassword123',
            dni='99999999'
        )
        self.teacher = PersonalDocente.objects.create_user(
            username='teacheruser',
            password='teacherpassword123',
            dni='88888888'
        )
        self.tipo_doc = TipoDocumento.objects.create(nombre='Test Type')
        self.document = Documento.objects.create(
            titulo='Test Document',
            docente=self.teacher,
            tipo_documento=self.tipo_doc
        )
        self.client = Client()

    def test_notification_creation_on_status_change(self):
        """Test that a notification is created when a document's status changes."""
        # Check that there are no notifications initially
        self.assertEqual(Notificacion.objects.count(), 0)

        # Change the document status and save it
        self.document.estado = 'APROBADO'
        self.document.save()

        # Check that one notification has been created
        self.assertEqual(Notificacion.objects.count(), 1)
        notification = Notificacion.objects.first()
        self.assertEqual(notification.destinatario, self.teacher)
        self.assertIn('aprobado', notification.mensaje)

        # Test the 'OBSERVADO' case
        self.document.estado = 'OBSERVADO'
        self.document.save()
        self.assertEqual(Notificacion.objects.count(), 2)
        notification = Notificacion.objects.latest('fecha_creacion')
        self.assertEqual(notification.destinatario, self.teacher)
        self.assertIn('observaciones', notification.mensaje)

    def test_notification_indicator_and_mark_as_read(self):
        """Test the notification indicator and that notifications are marked as read."""
        # Create a notification manually for the teacher
        Notificacion.objects.create(destinatario=self.teacher, mensaje="Test notification")

        # Log in as the teacher
        self.client.login(username='teacheruser', password='teacherpassword123')

        # 1. Check the dashboard for the unread count
        dashboard_url = reverse('dashboard')
        response = self.client.get(dashboard_url)
        self.assertContains(response, '<span class="badge badge-sm badge-primary indicator-item">1</span>')

        # 2. Visit the notifications page
        notifications_url = reverse('ver_notificaciones')
        response = self.client.get(notifications_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test notification")

        # 3. Check that the notification is now marked as read
        self.assertEqual(Notificacion.objects.filter(destinatario=self.teacher, leido=True).count(), 1)

        # 4. Check the dashboard again, the count should be gone
        response = self.client.get(dashboard_url)
        self.assertNotContains(response, 'indicator-item')


class ReporteAsistenciaTest(TestCase):

    def setUp(self):
        """Set up a staff user and a regular user for testing."""
        self.staff_user = PersonalDocente.objects.create_superuser(
            username='staffuser',
            password='staffpassword123',
            dni='87654321',
            first_name='Staff',
            last_name='User'
        )
        self.docente = PersonalDocente.objects.create_user(
            username='testdocente',
            password='testpassword123',
            dni='12345678',
            first_name='Test',
            last_name='Docente'
        )
        self.client = Client()
        self.client.login(username='staffuser', password='staffpassword123')
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Software")

    def test_get_detalle_docente_api(self):
        """
        Test the API endpoint that retrieves detailed attendance info for the modal.
        """
        # URL for the detail API
        url = reverse('api:detalle_asistencia_docente_ajax', args=[self.docente.id])

        # Make the request
        response = self.client.get(url)

        # Check that the response is successful and is JSON
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        # Parse the JSON and check the new standardized structure
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)

        response_data = data['data']
        self.assertIn('docente', response_data)
        self.assertIn('asistencias_cursos', response_data)
        self.assertEqual(response_data['docente']['nombre_completo'], 'Test Docente')
        self.assertEqual(response_data['docente']['dni'], '12345678')

    def test_reporte_asistencia_logic(self):
        """
        Test the core logic of the attendance report for Presente, Tardanza, and Falta.
        """
        # 1. Setup
        today = date.today()
        # Ensure today is a Monday for predictability
        today = today - timedelta(days=today.weekday())

        Semestre.objects.create(nombre="Test Semestre", fecha_inicio=today-timedelta(days=30), fecha_fin=today+timedelta(days=30), estado='ACTIVO')
        config = ConfiguracionInstitucion.load()
        config.tiempo_limite_tardanza = 15
        config.save()

        curso_manana = Curso.objects.create(
            docente=self.docente,
            nombre="Curso de Mañana",
            dia='Lunes', # Corresponds to the adjusted `today`
            horario_inicio="09:00:00",
            horario_fin="11:00:00",
            semestre=Semestre.objects.first(),
            carrera=self.carrera
        )

        # 2. Test "Falta" (Absent)
        url = reverse('reporte_asistencia') + f'?fecha_inicio={today}&fecha_fin={today}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context['page_obj'].object_list
        # Find the record for our specific teacher and day
        docente_report = next((r for r in report_data if r['docente'] == self.docente and r['fecha'] == today), None)
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report['estado'], 'Falta')

        # 3. Test "Presente" (Present)
        Asistencia.objects.create(
            docente=self.docente,
            curso=curso_manana,
            fecha=today,
            hora_entrada=make_aware(timezone.datetime.combine(today, time(9, 5))) # On time
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context['page_obj'].object_list
        docente_report = next((r for r in report_data if r['docente'] == self.docente and r['fecha'] == today), None)
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report['estado'], 'Presente')

        # 4. Test "Tardanza" (Late)
        Asistencia.objects.all().delete() # Clear previous attendance
        Asistencia.objects.create(
            docente=self.docente,
            curso=curso_manana,
            fecha=today,
            hora_entrada=make_aware(timezone.datetime.combine(today, time(9, 20))) # 20 mins late
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context['page_obj'].object_list
        docente_report = next((r for r in report_data if r['docente'] == self.docente and r['fecha'] == today), None)
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report['estado'], 'Tardanza')

        # 5. Test "No Requerido"
        # Check for Tuesday, when there are no classes scheduled
        tuesday = today + timedelta(days=1)
        url = reverse('reporte_asistencia') + f'?fecha_inicio={tuesday}&fecha_fin={tuesday}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        report_data = response.context['page_obj'].object_list
        # By default (filter='todos'), the "No Requerido" status should be present.
        docente_report = next((r for r in report_data if r['docente'] == self.docente and r['fecha'] == tuesday), None)
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report['estado'], 'No Requerido')

        # Now check with a different filter, it should not be present
        url_presente = url + '&estado=presente'
        response = self.client.get(url_presente)
        report_data = response.context['page_obj'].object_list
        docente_report = next((r for r in report_data if r['docente'] == self.docente and r['fecha'] == tuesday), None)
        self.assertIsNone(docente_report)


class JustificacionTest(TestCase):

    def setUp(self):
        """Set up users and objects for justification tests."""
        self.staff_user = PersonalDocente.objects.create_superuser(
            username='staffuser_just',
            password='staffpassword123',
            dni='11112222'
        )
        self.teacher = PersonalDocente.objects.create_user(
            username='teacher_just',
            password='teacherpassword123',
            dni='33334444',
            first_name='Justo',
            last_name='Profesor'
        )
        self.tipo_justificacion = TipoJustificacion.objects.create(nombre="Licencia Médica")
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
            estado='PENDIENTE'
        )
        self.assertEqual(Justificacion.objects.count(), 1)
        self.assertEqual(justificacion.docente.first_name, "Justo")
        self.assertEqual(justificacion.get_estado_display(), "Pendiente")

    def test_solicitar_justificacion_view_for_teacher(self):
        """Test that a teacher can access and submit the justification form."""
        self.client.login(username='teacher_just', password='teacherpassword123')
        url = reverse('solicitar_justificacion')

        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nueva Solicitud de Justificación")

        # Test POST request
        today = date.today()
        post_data = {
            'tipo': self.tipo_justificacion.id,
            'fecha_inicio': today.strftime('%Y-%m-%d'),
            'fecha_fin': (today + timedelta(days=2)).strftime('%Y-%m-%d'),
            'motivo': 'Congreso académico'
        }
        response = self.client.post(url, post_data)

        # Should redirect to the list view after successful submission
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('lista_justificaciones'))
        self.assertEqual(Justificacion.objects.count(), 1)
        self.assertEqual(Justificacion.objects.first().motivo, 'Congreso académico')

    def test_lista_justificaciones_view_for_staff(self):
        """Test that a staff member can view and approve/reject justifications."""
        self.client.login(username='staffuser_just', password='staffpassword123')

        justificacion = Justificacion.objects.create(
            docente=self.teacher,
            tipo=self.tipo_justificacion,
            fecha_inicio=date.today(),
            fecha_fin=date.today(),
            motivo="Test motivo",
            estado='PENDIENTE'
        )

        url = reverse('lista_justificaciones')

        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestionar Justificaciones")
        self.assertContains(response, "Justo Profesor")

        # Test POST request to approve
        response = self.client.post(url, {'justificacion_id': justificacion.id, 'accion': 'aprobar'})
        self.assertEqual(response.status_code, 302)
        justificacion.refresh_from_db()
        self.assertEqual(justificacion.estado, 'APROBADO')
        self.assertEqual(justificacion.revisado_por, self.staff_user)

        # Test POST request to reject
        justificacion.estado = 'PENDIENTE'
        justificacion.save()
        response = self.client.post(url, {'justificacion_id': justificacion.id, 'accion': 'rechazar'})
        self.assertEqual(response.status_code, 302)
        justificacion.refresh_from_db()
        self.assertEqual(justificacion.estado, 'RECHAZADO')

    def test_reporte_asistencia_with_justificacion(self):
        """
        Test that an approved justification correctly changes the status from 'Falta' to 'Justificado'.
        """
        self.client.login(username='staffuser_just', password='staffpassword123')
        today = date.today()
        # Ensure today is a Monday for predictability
        today = today - timedelta(days=today.weekday())

        Semestre.objects.create(nombre="Test Semestre Just", fecha_inicio=today-timedelta(days=30), fecha_fin=today+timedelta(days=30), estado='ACTIVO')
        carrera = Carrera.objects.create(nombre="Ingeniería de Justificaciones")
        Curso.objects.create(
            docente=self.teacher,
            nombre="Curso con Falta",
            dia='Lunes',
            horario_inicio="14:00:00",
            horario_fin="16:00:00",
            semestre=Semestre.objects.first(),
            carrera=carrera
        )

        # 1. First, confirm the status is 'Falta' without justification
        url = reverse('reporte_asistencia') + f'?fecha_inicio={today}&fecha_fin={today}'
        response = self.client.get(url)
        report_data = response.context['page_obj'].object_list
        docente_report = next((r for r in report_data if r['docente'] == self.teacher and r['fecha'] == today), None)
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report['estado'], 'Falta')

        # 2. Now, add an approved justification for that day
        Justificacion.objects.create(
            docente=self.teacher,
            tipo=self.tipo_justificacion,
            fecha_inicio=today,
            fecha_fin=today,
            motivo="Ausencia justificada",
            estado='APROBADO',
            revisado_por=self.staff_user
        )

        # 3. Re-fetch the report and check that the status is now 'Justificado'
        response = self.client.get(url)
        report_data = response.context['page_obj'].object_list
        docente_report = next((r for r in report_data if r['docente'] == self.teacher and r['fecha'] == today), None)
        self.assertIsNotNone(docente_report)
        self.assertEqual(docente_report['estado'], 'Justificado')


from unittest.mock import patch

class RfidAsistenciaTest(TestCase):

    def setUp(self):
        """Set up a test user with an RFID UID and a client."""
        self.rfid_uid = "0A:1B:2C:3D"
        self.docente = PersonalDocente.objects.create(
            username='rfiduser',
            password='rfidpassword',
            dni='87654321',
            first_name='RFID',
            last_name='User',
            rfid_uid=self.rfid_uid
        )
        self.client = Client()
        self.url = reverse('api:asistencia_rfid')

    @patch('django.utils.timezone.now')
    def test_registrar_asistencia_rfid_success(self, mock_now):
        """Test successful attendance registration via RFID on a weekday."""
        # Mock 'now' to be a weekday
        mock_now.return_value = make_aware(timezone.datetime(2023, 10, 26, 10, 0, 0)) # A Thursday

        self.assertEqual(AsistenciaDiaria.objects.count(), 0)
        payload = json.dumps({'uid': self.rfid_uid})
        response = self.client.post(self.url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('teacher', response_data)
        self.assertEqual(response_data['teacher']['name'], 'RFID User')
        self.assertEqual(AsistenciaDiaria.objects.count(), 1)

        asistencia = AsistenciaDiaria.objects.first()
        self.assertEqual(asistencia.docente, self.docente)
        self.assertEqual(asistencia.fecha, date(2023, 10, 26))

    @patch('django.utils.timezone.now')
    def test_registrar_asistencia_rfid_duplicate(self, mock_now):
        """Test that duplicate attendance registration is prevented."""
        mock_now.return_value = make_aware(timezone.datetime(2023, 10, 26, 10, 0, 0))
        # First registration
        self.client.post(self.url, data=json.dumps({'uid': self.rfid_uid}), content_type='application/json')
        self.assertEqual(AsistenciaDiaria.objects.count(), 1)

        # Second (duplicate) registration
        response = self.client.post(self.url, data=json.dumps({'uid': self.rfid_uid}), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'warning')
        self.assertIn('teacher', response_data)
        self.assertEqual(AsistenciaDiaria.objects.count(), 1)

    @patch('django.utils.timezone.now')
    def test_registrar_asistencia_rfid_not_found(self, mock_now):
        """Test registration with an unregistered RFID UID."""
        # Mock 'now' to be a weekday to bypass the weekend check
        mock_now.return_value = make_aware(timezone.datetime(2023, 10, 26, 10, 0, 0)) # A Thursday

        payload = json.dumps({'uid': 'XX:XX:XX:XX'})
        response = self.client.post(self.url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('no reconocida', response.json()['message'])
        self.assertEqual(AsistenciaDiaria.objects.count(), 0)

    def test_registrar_asistencia_rfid_bad_request_no_uid(self):
        """Test registration with missing UID in payload."""
        payload = json.dumps({'other_key': 'some_value'})
        response = self.client.post(self.url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('Datos inválidos', response.json()['message'])

    @patch('django.utils.timezone.now')
    def test_registrar_asistencia_rfid_weekend(self, mock_now):
        """Test that attendance registration is blocked on weekends."""
        # Mock 'now' to be a Saturday
        mock_now.return_value = make_aware(timezone.datetime(2023, 10, 28, 10, 0, 0)) # A Saturday

        payload = json.dumps({'uid': self.rfid_uid})
        response = self.client.post(self.url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'weekend_off')
        self.assertEqual(AsistenciaDiaria.objects.count(), 0)


from django.core.management import call_command
from io import StringIO

from datetime import datetime

class AutoCheckoutTest(TestCase):

    def setUp(self):
        self.docente = PersonalDocente.objects.create_user(username='checkout_user', dni='87654321')
        self.carrera = Carrera.objects.create(nombre="Ingeniería de Checkout")
        self.semestre = Semestre.objects.create(nombre="Test Semestre Checkout", fecha_inicio=date.today()-timedelta(days=30), fecha_fin=date.today()+timedelta(days=30), estado='ACTIVO')

        self.curso_pasado = Curso.objects.create(
            docente=self.docente,
            nombre="Curso Pasado",
            dia='Lunes',
            horario_inicio=time(8, 0),
            horario_fin=time(10, 0),
            semestre=self.semestre,
            carrera=self.carrera
        )

        self.curso_futuro = Curso.objects.create(
            docente=self.docente,
            nombre="Curso Futuro",
            dia='Lunes',
            horario_inicio=time(18, 0),
            horario_fin=time(20, 0),
            semestre=self.semestre,
            carrera=self.carrera
        )

        # Create an attendance record for a course that has already ended today
        # but has no checkout time.
        self.asistencia_abierta = Asistencia.objects.create(
            docente=self.docente,
            curso=self.curso_pasado,
            fecha=date.today() - timedelta(days=7), # Last week
            hora_entrada=timezone.make_aware(datetime.combine(date.today() - timedelta(days=7), time(8, 5)))
        )

        # Create an attendance record for a course that has not yet ended today.
        self.asistencia_futura = Asistencia.objects.create(
            docente=self.docente,
            curso=self.curso_futuro,
            fecha=date.today(),
            hora_entrada=timezone.now()
        )

    @patch('django.utils.timezone.now')
    def test_auto_checkout_command(self, mock_now):
        """
        Test that the auto_checkout_courses command correctly closes open attendances
        for courses that have already ended.
        """
        # Mock 'now' to be a time after the past course has ended, but before the future one.
        mock_now.return_value = timezone.make_aware(datetime.combine(date.today(), time(12, 0)))

        out = StringIO()
        call_command('auto_checkout_courses', stdout=out)

        self.asistencia_abierta.refresh_from_db()
        self.asistencia_futura.refresh_from_db()

        # The open attendance for the past course should now be closed.
        self.assertIsNotNone(self.asistencia_abierta.hora_salida)

        # The exit time should be the scheduled end time of the course.
        expected_checkout_time = timezone.make_aware(
            datetime.combine(self.asistencia_abierta.fecha, self.curso_pasado.horario_fin)
        )
        self.assertEqual(self.asistencia_abierta.hora_salida, expected_checkout_time)

        # The open attendance for the future course should remain open.
        self.assertIsNone(self.asistencia_futura.hora_salida)

        self.assertIn("1 attendances were closed", out.getvalue())
