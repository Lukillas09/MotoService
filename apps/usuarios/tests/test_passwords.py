from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .utils import ruta_desde_email


class RecuperacionContrasenaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="lucia",
            password="Clave-anterior-123",
            email="lucia@example.com",
            is_active=True,
        )

    def solicitar(self, email, *, follow=False):
        return self.client.post(reverse("password_reset"), {"email": email}, follow=follow)

    def test_login_ofrece_recuperacion_y_no_registro_publico(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "¿Olvidaste tu contraseña?")
        for ruta in ("/signup/", "/register/", "/crear-cuenta/"):
            self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_email_existente_envia_enlace_sin_password(self):
        response = self.solicitar("LUCIA@example.com")
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)
        self.assertNotIn("Clave-anterior-123", mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND="apps.core.email_backends.ResendEmailBackend",
        RESEND_FROM_EMAIL="MotoService <onboarding@resend.dev>",
        DEFAULT_FROM_EMAIL="remitente@example.com",
        EMAIL_HOST_USER="cuenta-proveedor@example.com",
    )
    @patch("apps.core.email_backends.resend.Emails.send")
    def test_recuperacion_entrega_a_resend_el_email_del_usuario(self, resend_send):
        self.usuario.email = "usuario@example.com"
        self.usuario.save(update_fields=("email",))
        resend_send.return_value = {"id": "email-de-prueba"}

        response = self.solicitar("usuario@example.com")

        self.assertRedirects(response, reverse("password_reset_done"))
        resend_send.assert_called_once()
        payload = resend_send.call_args.args[0]
        self.assertEqual(payload["to"], ["usuario@example.com"])
        self.assertNotEqual(payload["to"], [settings.DEFAULT_FROM_EMAIL])
        self.assertNotEqual(payload["to"], [settings.EMAIL_HOST_USER])

    @override_settings(
        EMAIL_BACKEND="apps.core.email_backends.ResendEmailBackend",
        RESEND_FROM_EMAIL="MotoService <onboarding@resend.dev>",
    )
    @patch("apps.core.email_backends.resend.Emails.send")
    def test_fallo_resend_registra_metadatos_seguros(self, resend_send):
        class ErrorProveedorPrueba(Exception):
            error_type = "validation_error"
            code = 403

        resend_send.side_effect = ErrorProveedorPrueba(
            "Detalle privado usuario-secreto@example.com token-secreto"
        )

        with self.assertLogs("apps.core.email_backends", level="WARNING") as logs:
            with self.assertLogs("django.contrib.auth", level="ERROR") as auth_logs:
                response = self.solicitar("lucia@example.com", follow=True)

        registro = logs.output[0]
        error_registrado = auth_logs.records[0].exc_info[1]
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Si existe una cuenta asociada")
        self.assertIn("exception=ErrorProveedorPrueba", registro)
        self.assertIn("error_type=validation_error", registro)
        self.assertIn("code=403", registro)
        self.assertNotIn("usuario-secreto@example.com", registro)
        self.assertNotIn("token-secreto", registro)
        self.assertEqual(type(error_registrado).__name__, "ResendEmailDeliveryError")
        self.assertTrue(error_registrado.__suppress_context__)
        self.assertNotIn("usuario-secreto@example.com", str(error_registrado))
        self.assertNotIn("token-secreto", str(error_registrado))

    def test_email_inexistente_e_inactivo_muestran_respuesta_equivalente(self):
        contenido_existente = self.solicitar("lucia@example.com", follow=True).content
        mail.outbox.clear()
        contenido_inexistente = self.solicitar("nadie@example.com", follow=True).content
        self.assertEqual(contenido_existente, contenido_inexistente)
        self.assertEqual(len(mail.outbox), 0)

        self.usuario.is_active = False
        self.usuario.save(update_fields=("is_active",))
        contenido_inactivo = self.solicitar("lucia@example.com", follow=True).content
        self.assertEqual(contenido_inexistente, contenido_inactivo)
        self.assertEqual(len(mail.outbox), 0)

    def test_cuenta_pendiente_no_recibe_recuperacion_normal(self):
        pendiente = get_user_model().objects.create_user(
            username="pendiente", email="pendiente@example.com"
        )
        pendiente.set_unusable_password()
        pendiente.save(update_fields=("password",))
        response = self.solicitar("pendiente@example.com", follow=True)
        self.assertContains(response, "Si existe una cuenta asociada")
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_cambia_password_y_token_es_de_un_solo_uso(self):
        self.solicitar("lucia@example.com")
        ruta_original = ruta_desde_email(mail.outbox[0])
        response = self.client.get(ruta_original, follow=True)
        ruta_confirmacion = response.request["PATH_INFO"]
        self.client.post(
            ruta_confirmacion,
            {
                "new_password1": "Clave-nueva-segura-456",
                "new_password2": "Clave-nueva-segura-456",
            },
            follow=True,
        )
        self.assertFalse(
            self.client.login(username="lucia", password="Clave-anterior-123")
        )
        self.assertTrue(
            self.client.login(username="lucia", password="Clave-nueva-segura-456")
        )
        self.client.logout()
        response = self.client.get(ruta_original, follow=True)
        self.assertContains(response, "Este enlace ya no se puede usar")

    @patch("django.contrib.auth.forms.EmailMultiAlternatives.send", side_effect=OSError("smtp"))
    def test_fallo_smtp_no_revela_cuenta_ni_genera_500(self, _send):
        with self.assertLogs("django.contrib.auth", level="ERROR") as logs:
            response = self.solicitar("lucia@example.com", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Si existe una cuenta asociada")
        self.assertNotContains(response, "lucia@example.com")
        self.assertNotIn("lucia@example.com", logs.output[0])

    def test_duplicados_historicos_no_generan_emails_ambiguos(self):
        get_user_model().objects.create_user(
            username="otra", password="Otra-clave-123", email="LUCIA@example.com"
        )
        response = self.solicitar("lucia@example.com", follow=True)
        self.assertContains(response, "Si existe una cuenta asociada")
        self.assertEqual(len(mail.outbox), 0)

    def test_timeout_y_backend_de_test(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 86400)
        self.assertEqual(
            settings.EMAIL_BACKEND,
            "django.core.mail.backends.locmem.EmailBackend",
        )
