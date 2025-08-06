from django.test import TestCase, Client
from django.urls import reverse
from .models import PersonalDocente
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
