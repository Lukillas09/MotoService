from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.roles import GRUPO_PROPIETARIO


class PermisosUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.usuario = User.objects.create_user(
            username="operador", password="Clave-segura-123"
        )
        cls.propietario = User.objects.create_user(
            username="dueno", password="Clave-segura-123"
        )
        grupo = Group.objects.create(name=GRUPO_PROPIETARIO)
        cls.propietario.groups.add(grupo)
        cls.superuser = User.objects.create_superuser(
            username="admin", password="Clave-segura-123", email="admin@example.com"
        )

    def test_no_autenticado_es_redirigido_al_login(self):
        ruta = reverse("usuarios:list")
        response = self.client.get(ruta)
        self.assertRedirects(response, f"{reverse('login')}?next={ruta}")

    def test_usuario_normal_recibe_403(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("usuarios:list")).status_code, 403)

    def test_propietario_por_group_tiene_acceso(self):
        self.client.force_login(self.propietario)
        self.assertEqual(self.client.get(reverse("usuarios:list")).status_code, 200)

    def test_superuser_es_propietario_sin_necesitar_group(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("usuarios:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Propietario")

    def test_se_conserva_el_user_estandar_de_django(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "auth.User")

    def test_usuario_normal_no_puede_crear_por_post(self):
        self.client.force_login(self.usuario)
        cantidad = get_user_model().objects.count()
        response = self.client.post(
            reverse("usuarios:create"),
            {
                "first_name": "Invitado",
                "last_name": "Demo",
                "username": "invitado",
                "email": "invitado@example.com",
                "rol": "USUARIO",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(get_user_model().objects.count(), cantidad)

    def test_navegacion_oculta_usuarios_y_muestra_mi_cuenta_segun_rol(self):
        self.client.force_login(self.usuario)
        contenido_usuario = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn(reverse("usuarios:cuenta"), contenido_usuario)
        self.assertNotIn(reverse("usuarios:list"), contenido_usuario)

        self.client.force_login(self.propietario)
        contenido_propietario = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn(reverse("usuarios:cuenta"), contenido_propietario)
        self.assertIn(reverse("usuarios:list"), contenido_propietario)
