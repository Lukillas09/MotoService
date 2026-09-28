from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.motos.models import Moto
from apps.servicios.models import Servicio
from apps.usuarios.roles import GRUPO_PROPIETARIO

from .utils import ruta_desde_email


class GestionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.propietario = User.objects.create_user(
            username="dueno",
            password="Clave-segura-123",
            email="dueno@example.com",
        )
        cls.grupo = Group.objects.create(name=GRUPO_PROPIETARIO)
        cls.propietario.groups.add(cls.grupo)

    def setUp(self):
        self.client.force_login(self.propietario)

    def datos_usuario(self, **cambios):
        datos = {
            "first_name": "Juan",
            "last_name": "Pérez",
            "username": "juan",
            "email": "Juan@Example.com",
            "rol": "USUARIO",
        }
        datos.update(cambios)
        return datos

    def crear_desde_vista(self, **cambios):
        return self.client.post(reverse("usuarios:create"), self.datos_usuario(**cambios))

    def test_crea_usuario_pendiente_y_envia_invitacion(self):
        response = self.crear_desde_vista()

        self.assertRedirects(response, reverse("usuarios:list"))
        usuario = get_user_model().objects.get(username="juan")
        self.assertEqual(usuario.first_name, "Juan")
        self.assertEqual(usuario.last_name, "Pérez")
        self.assertEqual(usuario.email, "juan@example.com")
        self.assertTrue(usuario.is_active)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.has_usable_password())
        self.assertFalse(usuario.groups.filter(name=GRUPO_PROPIETARIO).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Tu acceso a MotoService", mail.outbox[0].subject)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)
        self.assertNotIn("Clave-segura-123", mail.outbox[0].body)

    def test_crear_propietario_garantiza_group_sin_cambiar_staff(self):
        superuser = get_user_model().objects.create_superuser(
            username="admin-creador",
            password="Clave-segura-123",
            email="admin-creador@example.com",
        )
        Group.objects.filter(name=GRUPO_PROPIETARIO).delete()
        self.client.force_login(superuser)
        self.crear_desde_vista(username="encargada", email="encargada@example.com", rol="PROPIETARIO")
        usuario = get_user_model().objects.get(username="encargada")
        self.assertTrue(usuario.groups.filter(name=GRUPO_PROPIETARIO).exists())
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_email_es_unico_sin_distinguir_mayusculas(self):
        get_user_model().objects.create_user(
            username="existente", email="  juan@example.com  "
        )
        cantidad = get_user_model().objects.count()
        response = self.crear_desde_vista(email="JUAN@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un usuario con este correo electrónico")
        self.assertEqual(get_user_model().objects.count(), cantidad)

    @patch("apps.usuarios.services.EmailMultiAlternatives.send", side_effect=OSError("smtp"))
    def test_fallo_de_email_deja_usuario_pendiente_y_no_genera_500(self, _send):
        with self.assertLogs("apps.usuarios.services", level="WARNING") as logs:
            response = self.crear_desde_vista()
        self.assertRedirects(response, reverse("usuarios:list"))
        self.assertTrue(get_user_model().objects.filter(username="juan").exists())
        usuario = get_user_model().objects.get(username="juan")
        self.assertFalse(usuario.has_usable_password())
        self.assertIn("usuario_id=", logs.output[0])
        self.assertNotIn("juan@example.com", logs.output[0])

    def test_invitacion_permite_elegir_password_y_luego_iniciar_sesion(self):
        self.crear_desde_vista()
        usuario = get_user_model().objects.get(username="juan")
        self.client.logout()
        self.assertFalse(
            self.client.login(username="juan", password="Nueva-clave-segura-456")
        )

        ruta = ruta_desde_email(mail.outbox[0])
        response = self.client.get(ruta, follow=True)
        self.assertContains(response, "Elegí una nueva contraseña")
        ruta_confirmacion = response.request["PATH_INFO"]
        response = self.client.post(
            ruta_confirmacion,
            {
                "new_password1": "Nueva-clave-segura-456",
                "new_password2": "Nueva-clave-segura-456",
            },
            follow=True,
        )
        self.assertContains(response, "Tu contraseña fue actualizada")
        usuario.refresh_from_db()
        self.assertTrue(usuario.has_usable_password())
        self.assertTrue(
            self.client.login(username="juan", password="Nueva-clave-segura-456")
        )

    def test_reenviar_invitacion_invalida_el_enlace_anterior(self):
        self.crear_desde_vista()
        usuario = get_user_model().objects.get(username="juan")
        enlace_anterior = ruta_desde_email(mail.outbox[0])
        response = self.client.post(
            reverse("usuarios:resend_invitation", args=[usuario.pk])
        )
        self.assertRedirects(response, reverse("usuarios:list"))
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotEqual(enlace_anterior, ruta_desde_email(mail.outbox[1]))
        response = self.client.get(enlace_anterior, follow=True)
        self.assertContains(response, "Este enlace ya no se puede usar")

    def test_editar_email_pendiente_invalida_y_reenvia_invitacion(self):
        self.crear_desde_vista()
        usuario = get_user_model().objects.get(username="juan")
        enlace_anterior = ruta_desde_email(mail.outbox[0])
        response = self.client.post(
            reverse("usuarios:update", args=[usuario.pk]),
            self.datos_usuario(email="nuevo@example.com"),
        )
        self.assertRedirects(response, reverse("usuarios:list"))
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, "nuevo@example.com")
        self.assertEqual(len(mail.outbox), 2)
        self.assertContains(
            self.client.get(enlace_anterior, follow=True),
            "Este enlace ya no se puede usar",
        )

    def test_acciones_mutantes_rechazan_get(self):
        usuario = get_user_model().objects.create_user(username="operador")
        for nombre in ("deactivate", "reactivate", "resend_invitation"):
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    self.client.get(reverse(f"usuarios:{nombre}", args=[usuario.pk])).status_code,
                    405,
                )

    def test_acciones_mutantes_exigen_csrf(self):
        usuario = get_user_model().objects.create_user(username="operador")
        cliente_csrf = Client(enforce_csrf_checks=True)
        cliente_csrf.force_login(self.propietario)
        for nombre in ("deactivate", "reactivate", "resend_invitation"):
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    cliente_csrf.post(
                        reverse(f"usuarios:{nombre}", args=[usuario.pk])
                    ).status_code,
                    403,
                )

    def test_acciones_mutantes_devuelven_404_para_usuario_inexistente(self):
        usuario_pk = get_user_model().objects.order_by("-pk").first().pk + 100
        for nombre in ("deactivate", "reactivate", "resend_invitation"):
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    self.client.post(
                        reverse(f"usuarios:{nombre}", args=[usuario_pk])
                    ).status_code,
                    404,
                )

    def test_desactivar_y_reactivar_no_elimina_historial(self):
        usuario = get_user_model().objects.create_user(
            username="mecanico",
            password="Clave-segura-123",
            email="mecanico@example.com",
        )
        cliente = Cliente.objects.create(nombre="Cliente Demo")
        moto = Moto.objects.create(cliente=cliente, marca="Moto", modelo="Demo")
        servicio = Servicio.objects.create(moto=moto, creado_por=usuario)

        self.client.post(reverse("usuarios:deactivate", args=[usuario.pk]))
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        self.assertEqual(Servicio.objects.get(pk=servicio.pk).creado_por, usuario)
        self.assertTrue(get_user_model().objects.filter(pk=usuario.pk).exists())

        self.client.post(reverse("usuarios:reactivate", args=[usuario.pk]))
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)

    def test_no_permite_desactivar_ni_degradar_al_ultimo_propietario(self):
        response = self.client.post(
            reverse("usuarios:deactivate", args=[self.propietario.pk]), follow=True
        )
        self.assertContains(response, "al menos un Propietario activo")
        self.propietario.refresh_from_db()
        self.assertTrue(self.propietario.is_active)

        datos = {
            "first_name": self.propietario.first_name,
            "last_name": self.propietario.last_name,
            "username": self.propietario.username,
            "email": self.propietario.email,
            "rol": "USUARIO",
        }
        response = self.client.post(
            reverse("usuarios:update", args=[self.propietario.pk]), datos
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "al menos un Propietario activo")
        self.assertTrue(
            self.propietario.groups.filter(name=GRUPO_PROPIETARIO).exists()
        )

    def test_con_dos_propietarios_se_puede_desactivar_uno(self):
        segundo = get_user_model().objects.create_user(
            username="segundo",
            password="Clave-segura-123",
            email="segundo@example.com",
        )
        segundo.groups.add(self.grupo)
        self.client.post(reverse("usuarios:deactivate", args=[segundo.pk]))
        segundo.refresh_from_db()
        self.assertFalse(segundo.is_active)
        self.assertTrue(self.propietario.is_active)

    def test_con_dos_propietarios_se_puede_degradar_uno(self):
        segundo = get_user_model().objects.create_user(
            username="segundo",
            password="Clave-segura-123",
            email="segundo@example.com",
        )
        segundo.groups.add(self.grupo)

        response = self.client.post(
            reverse("usuarios:update", args=[segundo.pk]),
            self.datos_usuario(
                username=segundo.username,
                email=segundo.email,
                rol="USUARIO",
            ),
        )

        self.assertRedirects(response, reverse("usuarios:list"))
        segundo.refresh_from_db()
        self.assertFalse(
            segundo.groups.filter(name=GRUPO_PROPIETARIO).exists()
        )
        self.assertTrue(
            self.propietario.groups.filter(name=GRUPO_PROPIETARIO).exists()
        )

    def test_propietario_normal_no_puede_administrar_superuser(self):
        superuser = get_user_model().objects.create_superuser(
            username="root", password="Clave-segura-123", email="root@example.com"
        )
        self.assertEqual(
            self.client.get(reverse("usuarios:update", args=[superuser.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("usuarios:deactivate", args=[superuser.pk])).status_code,
            403,
        )
        superuser.refresh_from_db()
        self.assertTrue(superuser.is_active)

    def test_inactivo_debe_reactivarse_antes_de_reenviar_invitacion(self):
        usuario = get_user_model().objects.create_user(
            username="pendiente", email="pendiente@example.com", is_active=False
        )
        usuario.set_unusable_password()
        usuario.save(update_fields=("password",))
        response = self.client.post(
            reverse("usuarios:resend_invitation", args=[usuario.pk]), follow=True
        )
        self.assertContains(response, "Primero reactivá el usuario")
        self.assertEqual(len(mail.outbox), 0)
