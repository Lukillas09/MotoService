from copy import deepcopy
from unittest.mock import call, patch

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from apps.core.email_backends import (
    ResendEmailBackend,
    ResendEmailDeliveryError,
    ResendEmailMessageError,
)


@override_settings(
    RESEND_API_KEY="re_test_key",
    RESEND_FROM_EMAIL="MotoService <acceso@example.test>",
)
class ResendEmailBackendTests(SimpleTestCase):
    def setUp(self):
        patcher = patch("apps.core.email_backends.resend.Emails.send")
        self.resend_send = patcher.start()
        self.resend_send.return_value = {"id": "email_test"}
        self.addCleanup(patcher.stop)

    def test_envia_email_de_texto_plano(self):
        message = EmailMessage(
            subject="Invitación",
            body="Elegí tu contraseña.",
            to=["persona@example.test"],
        )

        sent_count = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)
        self.resend_send.assert_called_once_with(
            {
                "from": "MotoService <acceso@example.test>",
                "to": ["persona@example.test"],
                "subject": "Invitación",
                "text": "Elegí tu contraseña.",
            }
        )

    def test_envia_texto_y_alternativa_html(self):
        message = EmailMultiAlternatives(
            subject="Recuperación",
            body="Abrí el enlace para continuar.",
            to=["persona@example.test"],
        )
        message.attach_alternative(
            "<p>Abrí el <strong>enlace</strong> para continuar.</p>",
            "text/html",
        )

        sent_count = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)
        payload = self.resend_send.call_args.args[0]
        self.assertEqual(payload["text"], "Abrí el enlace para continuar.")
        self.assertEqual(
            payload["html"],
            "<p>Abrí el <strong>enlace</strong> para continuar.</p>",
        )

    @override_settings(
        EMAIL_BACKEND="apps.core.email_backends.ResendEmailBackend"
    )
    def test_emailmultialternatives_usa_el_backend_desde_la_api_de_django(self):
        message = EmailMultiAlternatives(
            subject="Invitación",
            body="Texto de invitación",
            to=["persona@example.test"],
        )
        message.attach_alternative("<p>Invitación</p>", "text/html")

        sent_count = message.send(fail_silently=False)

        self.assertEqual(sent_count, 1)
        self.assertEqual(
            self.resend_send.call_args.args[0],
            {
                "from": "MotoService <acceso@example.test>",
                "to": ["persona@example.test"],
                "subject": "Invitación",
                "text": "Texto de invitación",
                "html": "<p>Invitación</p>",
            },
        )

    def test_mapea_el_asunto(self):
        message = EmailMessage(
            subject="Asunto exacto",
            body="Contenido",
            to=["persona@example.test"],
        )

        ResendEmailBackend().send_messages([message])

        self.assertEqual(
            self.resend_send.call_args.args[0]["subject"],
            "Asunto exacto",
        )

    def test_usa_el_remitente_configurado_y_no_el_del_mensaje(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            from_email="otro@example.test",
            to=["persona@example.test"],
        )

        ResendEmailBackend().send_messages([message])

        self.assertEqual(
            self.resend_send.call_args.args[0]["from"],
            "MotoService <acceso@example.test>",
        )

    def test_mapea_destinatarios_to(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["uno@example.test", "dos@example.test"],
        )

        ResendEmailBackend().send_messages([message])

        self.assertEqual(
            self.resend_send.call_args.args[0]["to"],
            ["uno@example.test", "dos@example.test"],
        )

    def test_mapea_cc_y_bcc(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["principal@example.test"],
            cc=["copia@example.test"],
            bcc=["oculta@example.test"],
        )

        ResendEmailBackend().send_messages([message])

        payload = self.resend_send.call_args.args[0]
        self.assertEqual(payload["cc"], ["copia@example.test"])
        self.assertEqual(payload["bcc"], ["oculta@example.test"])

    def test_mapea_reply_to(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
            reply_to=["taller@example.test"],
        )

        ResendEmailBackend().send_messages([message])

        self.assertEqual(
            self.resend_send.call_args.args[0]["reply_to"],
            ["taller@example.test"],
        )

    def test_devuelve_la_cantidad_de_mensajes_enviados(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )

        sent_count = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)

    def test_envia_multiples_mensajes(self):
        first = EmailMessage(
            subject="Primero",
            body="Uno",
            to=["uno@example.test"],
        )
        second = EmailMessage(
            subject="Segundo",
            body="Dos",
            to=["dos@example.test"],
        )

        sent_count = ResendEmailBackend().send_messages([first, second])

        self.assertEqual(sent_count, 2)
        self.assertEqual(self.resend_send.call_count, 2)
        self.assertEqual(
            self.resend_send.call_args_list,
            [
                call(
                    {
                        "from": "MotoService <acceso@example.test>",
                        "to": ["uno@example.test"],
                        "subject": "Primero",
                        "text": "Uno",
                    }
                ),
                call(
                    {
                        "from": "MotoService <acceso@example.test>",
                        "to": ["dos@example.test"],
                        "subject": "Segundo",
                        "text": "Dos",
                    }
                ),
            ],
        )

    def test_propaga_error_sanitizado_cuando_fail_silently_es_false(self):
        provider_error = RuntimeError(
            "re_test_key Contenido sensible persona@example.test"
        )
        self.resend_send.side_effect = provider_error
        message = EmailMessage(
            subject="Asunto",
            body="Contenido sensible",
            to=["persona@example.test"],
        )

        with self.assertRaisesMessage(
            ResendEmailDeliveryError,
            "Email delivery through Resend failed.",
        ) as raised:
            ResendEmailBackend(fail_silently=False).send_messages([message])

        self.assertIsNone(raised.exception.__cause__)
        self.assertTrue(raised.exception.__suppress_context__)
        error_message = str(raised.exception)
        self.assertNotIn("re_test_key", error_message)
        self.assertNotIn("Contenido sensible", error_message)
        self.assertNotIn("persona@example.test", error_message)

    def test_oculta_error_de_api_y_hace_logging_seguro(self):
        self.resend_send.side_effect = RuntimeError(
            "re_test_key Contenido sensible persona@example.test"
        )
        message = EmailMessage(
            subject="Asunto",
            body="Contenido sensible",
            to=["persona@example.test"],
        )

        with self.assertLogs("apps.core.email_backends", level="WARNING") as logs:
            sent_count = ResendEmailBackend(fail_silently=True).send_messages(
                [message]
            )

        self.assertEqual(sent_count, 0)
        log_output = " ".join(logs.output)
        self.assertIn("RuntimeError", log_output)
        self.assertNotIn("re_test_key", log_output)
        self.assertNotIn("Contenido sensible", log_output)
        self.assertNotIn("persona@example.test", log_output)

    def test_omite_email_sin_destinatarios(self):
        message = EmailMessage(subject="Asunto", body="Contenido")

        sent_count = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 0)
        self.resend_send.assert_not_called()

    def test_rechaza_bcc_sin_destinatario_principal_sin_exponerlo(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            bcc=["oculta@example.test"],
        )

        with self.assertRaisesMessage(
            ResendEmailMessageError,
            "Resend requires at least one primary recipient in 'to'.",
        ):
            ResendEmailBackend(fail_silently=False).send_messages([message])

        self.resend_send.assert_not_called()

    def test_rechaza_adjuntos_cuando_fail_silently_es_false(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )
        message.attach("archivo.txt", "contenido", "text/plain")

        with self.assertRaisesMessage(
            NotImplementedError,
            "Attachments are not supported by ResendEmailBackend.",
        ):
            ResendEmailBackend(fail_silently=False).send_messages([message])

        self.resend_send.assert_not_called()

    def test_adjunto_falla_en_silencio_y_hace_logging_seguro(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )
        message.attach("secreto.txt", "contenido sensible", "text/plain")

        with self.assertLogs("apps.core.email_backends", level="WARNING") as logs:
            sent_count = ResendEmailBackend(fail_silently=True).send_messages(
                [message]
            )

        self.assertEqual(sent_count, 0)
        self.resend_send.assert_not_called()
        log_output = " ".join(logs.output)
        self.assertIn("NotImplementedError", log_output)
        self.assertNotIn("secreto.txt", log_output)
        self.assertNotIn("contenido sensible", log_output)

    def test_no_modifica_el_mensaje_original(self):
        message = EmailMultiAlternatives(
            subject="Asunto",
            body="Texto",
            from_email="original@example.test",
            to=["persona@example.test"],
            cc=["copia@example.test"],
            bcc=["oculta@example.test"],
            reply_to=["respuesta@example.test"],
        )
        message.attach_alternative("<p>HTML</p>", "text/html")
        original_state = deepcopy(message.__dict__)

        ResendEmailBackend().send_messages([message])

        self.assertEqual(message.__dict__, original_state)
