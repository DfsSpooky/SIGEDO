from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Docente


class JWTAuthTests(APITestCase):
    def setUp(self):
        self.docente = Docente.objects.create_user(
            username="testuser",
            password="testpassword",
            dni="12345678",
            first_name="Test",
            last_name="User",
        )
        self.token_url = reverse("api:token_obtain_pair")
        self.refresh_url = reverse("api:token_refresh")

    def test_get_token(self):
        """
        Ensure we can get a new token object using valid credentials.
        """
        data = {
            "username": "testuser",
            "password": "testpassword",
        }
        response = self.client.post(self.token_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_refresh_token(self):
        """
        Ensure we can refresh a token.
        """
        # First get a token
        data = {
            "username": "testuser",
            "password": "testpassword",
        }
        response = self.client.post(self.token_url, data, format="json")
        refresh_token = response.data["refresh"]

        # Now try to refresh it
        refresh_data = {"refresh": refresh_token}
        response_refresh = self.client.post(self.refresh_url, refresh_data, format="json")
        self.assertEqual(response_refresh.status_code, status.HTTP_200_OK)
        self.assertIn("access", response_refresh.data)
