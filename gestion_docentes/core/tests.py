from django.test import TestCase, Client
from django.urls import reverse
from .models import PersonalDocente, Notificacion, TipoDocumento, Documento, Anuncio
from .utils.encryption import encrypt_id, decrypt_id
import re

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


class AdminInterfaceTest(TestCase):

    def setUp(self):
        """Set up a staff user and a non-staff user."""
        self.staff_user = PersonalDocente.objects.create_superuser(
            username='staffuser',
            password='staffpassword123',
            dni='87654321'
        )
        self.non_staff_user = PersonalDocente.objects.create_user(
            username='normaluser',
            password='userpassword123',
            is_staff=False,
            dni='11223344'
        )
        self.client = Client()

    def test_admin_dashboard_accessible_by_staff(self):
        """Test that the admin dashboard is accessible to staff members."""
        self.client.login(username='staffuser', password='staffpassword123')
        url = reverse('admin_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenido al Panel de Control de Administración")

    def test_admin_dashboard_inaccessible_by_non_staff(self):
        """Test that the admin dashboard is not accessible to non-staff members."""
        self.client.login(username='normaluser', password='userpassword123')
        url = reverse('admin_dashboard')
        response = self.client.get(url)
        # Should redirect to the normal user dashboard or login page
        self.assertNotEqual(response.status_code, 200)

    def test_rotate_qr_code_view(self):
        """Test that the rotate_qr_code view changes the id_qr."""
        self.client.login(username='staffuser', password='staffpassword123')

        # Get the initial QR ID
        initial_qr_id = self.staff_user.id_qr

        # Call the rotation view
        url = reverse('rotate_qr_code', args=[self.staff_user.id])
        response = self.client.get(url)

        # Check for a successful redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('admin:core_personaldocente_change', args=[self.staff_user.id]))

        # Refresh the user from the database and check if the QR ID has changed
        self.staff_user.refresh_from_db()
        self.assertNotEqual(initial_qr_id, self.staff_user.id_qr)


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
