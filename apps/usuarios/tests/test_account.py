from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.roles import GRUPO_PROPIETARIO


class MiCuentaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="maria",
            password="Clave-anterior-123",
            first_name="María",
            email="maria@example.com",
            is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_requiere_login_y_muestra_datos(self):
        self.client.logout()
        ruta = reverse("usuarios:cuenta")
        self.assertRedirects(self.client.get(ruta), f"{reverse('login')}?next={ruta}")
        self.client.force_login(self.usuario)
        response = self.client.get(ruta)
        self.assertContains(response, "Mi cuenta")
        self.assertContains(response, "maria")
        self.assertContains(response, "Usuario")

    def test_usuario_existente_sin_email_puede_entrar_y_ve_aviso(self):
        self.usuario.email = ""
        self.usuario.save(update_fields=("email",))
        response = self.client.get(reverse("usuarios:cuenta"))
        self.assertContains(response, "No tenés un correo configurado")

    def test_actualiza_nombre_sin_exponer_privilegios(self):
        response = self.client.post(
            reverse("usuarios:cuenta"),
            {
                "first_name": "Mariana",
                "last_name": "Demo",
                "email": "maria@example.com",
                "is_staff": "",
                "is_superuser": "on",
                "rol": "PROPIETARIO",
            },
        )
        self.assertRedirects(response, reverse("usuarios:cuenta"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Mariana")
        self.assertEqual(self.usuario.last_name, "Demo")
        self.assertTrue(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)
        self.assertFalse(
            self.usuario.groups.filter(name=GRUPO_PROPIETARIO).exists()
        )

    def test_cambiar_email_exige_password_actual_y_normaliza(self):
        datos = {
            "first_name": "María",
            "last_name": "",
            "email": "NUEVO@Example.com",
            "contrasena_actual": "incorrecta",
        }
        response = self.client.post(reverse("usuarios:cuenta"), datos)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresá tu contraseña actual")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "maria@example.com")

        datos["contrasena_actual"] = "Clave-anterior-123"
        response = self.client.post(reverse("usuarios:cuenta"), datos)
        self.assertRedirects(response, reverse("usuarios:cuenta"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "nuevo@example.com")

    def test_no_permite_email_duplicado(self):
        get_user_model().objects.create_user(
            username="otra", email="ocupado@example.com"
        )
        response = self.client.post(
            reverse("usuarios:cuenta"),
            {
                "first_name": "María",
                "last_name": "",
                "email": "OCUPADO@example.com",
                "contrasena_actual": "Clave-anterior-123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un usuario con este correo electrónico")

    def test_cambio_de_password_mantiene_sesion(self):
        response = self.client.post(
            reverse("usuarios:cambiar_contrasena"),
            {
                "old_password": "Clave-anterior-123",
                "new_password1": "Clave-nueva-segura-456",
                "new_password2": "Clave-nueva-segura-456",
            },
        )
        self.assertRedirects(response, reverse("usuarios:cuenta"))
        self.assertEqual(self.client.get(reverse("usuarios:cuenta")).status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Clave-nueva-segura-456"))

    def test_propietario_ve_su_rol_en_mi_cuenta(self):
        grupo = Group.objects.create(name=GRUPO_PROPIETARIO)
        self.usuario.groups.add(grupo)
        response = self.client.get(reverse("usuarios:cuenta"))
        self.assertContains(response, "Propietario")

