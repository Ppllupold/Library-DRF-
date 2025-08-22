from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

USER_REGISTER = reverse_lazy("users:register")
MANAGE_USER = reverse_lazy("users:manage-me")

User = get_user_model()


class UserTestCase(APITestCase):
    def setUp(self):
        self.user_auth = User.objects.create_superuser(
            email="admin@example.com", password="StrongPass123!"
        )
        self.client = APIClient()

    def test_register_allow_any_user(self):
        payload = {"email": "newuser@example.com", "password": "StrongPass123!"}
        response = self.client.post(USER_REGISTER, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=payload["email"]).exists())

        self.assertIn("id", response.data)
        self.assertIn("email", response.data)
        self.assertNotIn("password", response.data)

    def test_manage_me_requires_auth(self):
        response = self.client.get(MANAGE_USER)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        self.client.force_authenticate(user=self.user_auth)
        response = self.client.get(MANAGE_USER)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
