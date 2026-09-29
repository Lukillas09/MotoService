from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from brevo.core.api_error import ApiError
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from apps.core.email_backends import (
    BrevoEmailBackend,
    BrevoEmailDeliveryError,
    BrevoEmailMessageError,
)


@override_settings(
    BREVO_API_KEY="test-only-brevo-api-key",
    BREVO_FROM_EMAIL="acceso@example.test",
    BREVO_FROM_NAME="MotoService",
)
class BrevoEmailBackendTests(SimpleTestCase):
    def setUp(self):
        patcher = patch("apps.core.email_backends.Brevo")
        self.brevo_class = patcher.start()
        self.brevo_send = (
            self.brevo_class.return_value.transactional_emails.send_transac_email
        )
        self.brevo_send.return_value = SimpleNamespace(
            message_id="brevo-message-test"
        )
        self.addCleanup(patcher.stop)

    @staticmethod
    def address_values(addresses):
        return [(address.email, address.name) for address in addresses]

    def last_call_kwargs(self):
        self.brevo_send.assert_called_once()
        return self.brevo_send.call_args.kwargs

    def test_configura_cliente_oficial_con_api_key_y_timeout(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )

        BrevoEmailBackend().send_messages([message])

        self.brevo_class.assert_called_once_with(
            api_key="test-only-brevo-api-key",
            timeout=10.0,
        )

    def test_envia_email_de_texto_plano(self):
        message = EmailMessage(
            subject="Invitación",
            body="Elegí tu contraseña.",
            to=["persona@example.test"],
        )

        sent_count = BrevoEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)
        kwargs = self.last_call_kwargs()
        self.assertEqual(kwargs["subject"], "Invitación")
        self.assertEqual(kwargs["text_content"], "Elegí tu contraseña.")
        self.assertNotIn("html_content", kwargs)
        self.assertEqual(
            self.address_values(kwargs["to"]),
            [("persona@example.test", None)],
        )

    def test_conserva_message_id_de_brevo_en_la_conexion(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )
        backend = BrevoEmailBackend()

        sent_count = backend.send_messages([message])

        self.assertEqual(sent_count, 1)
        self.assertEqual(backend.message_ids, ["brevo-message-test"])

    def test_envia_email_html(self):
        message = EmailMessage(
            subject="Aviso",
            body="<p>Contenido <strong>HTML</strong></p>",
            to=["persona@example.test"],
        )
        message.content_subtype = "html"

        sent_count = BrevoEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)
        kwargs = self.last_call_kwargs()
        self.assertEqual(
            kwargs["html_content"],
            "<p>Contenido <strong>HTML</strong></p>",
        )
        self.assertNotIn("text_content", kwargs)

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

        sent_count = BrevoEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)
        kwargs = self.last_call_kwargs()
        self.assertEqual(
            kwargs["text_content"],
            "Abrí el enlace para continuar.",
        )
        self.assertEqual(
            kwargs["html_content"],
            "<p>Abrí el <strong>enlace</strong> para continuar.</p>",
        )

    def test_admite_alternativa_como_tupla_de_django_5_1(self):
        message = EmailMultiAlternatives(
            subject="Asunto",
            body="Contenido de texto",
            to=["persona@example.test"],
        )
        message.alternatives = [("<p>Contenido HTML</p>", "text/html")]

        BrevoEmailBackend().send_messages([message])

        kwargs = self.last_call_kwargs()
        self.assertEqual(kwargs["text_content"], "Contenido de texto")
        self.assertEqual(kwargs["html_content"], "<p>Contenido HTML</p>")

    def test_admite_alternativa_como_tupla_de_django_5_1(self):
        message = EmailMultiAlternatives(
            subject="Asunto",
            body="Contenido de texto",
            to=["persona@example.test"],
        )
        message.alternatives = [("<p>Contenido HTML</p>", "text/html")]

        BrevoEmailBackend().send_messages([message])

        kwargs = self.last_call_kwargs()
        self.assertEqual(kwargs["text_content"], "Contenido de texto")
        self.assertEqual(kwargs["html_content"], "<p>Contenido HTML</p>")

    @override_settings(
        EMAIL_BACKEND="apps.core.email_backends.BrevoEmailBackend"
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
        kwargs = self.last_call_kwargs()
        self.assertEqual(kwargs["subject"], "Invitación")
        self.assertEqual(kwargs["text_content"], "Texto de invitación")
        self.assertEqual(kwargs["html_content"], "<p>Invitación</p>")
        self.assertEqual(
            self.address_values(kwargs["to"]),
            [("persona@example.test", None)],
        )

    def test_usa_el_remitente_configurado_y_no_el_del_mensaje(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            from_email="otro@example.test",
            to=["persona@example.test"],
        )

        BrevoEmailBackend().send_messages([message])

        sender = self.last_call_kwargs()["sender"]
        self.assertEqual(sender.email, "acceso@example.test")
        self.assertEqual(sender.name, "MotoService")

    def test_mapea_to_cc_bcc_y_nombres(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["Persona Uno <uno@example.test>", "dos@example.test"],
            cc=["Copia <copia@example.test>"],
            bcc=["Oculta <oculta@example.test>"],
        )

        BrevoEmailBackend().send_messages([message])

        kwargs = self.last_call_kwargs()
        self.assertEqual(
            self.address_values(kwargs["to"]),
            [
                ("uno@example.test", "Persona Uno"),
                ("dos@example.test", None),
            ],
        )
        self.assertEqual(
            self.address_values(kwargs["cc"]),
            [("copia@example.test", "Copia")],
        )
        self.assertEqual(
            self.address_values(kwargs["bcc"]),
            [("oculta@example.test", "Oculta")],
        )

    def test_mapea_nombre_unicode_sin_codificacion_mime(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["José Álvarez <jose@example.test>"],
        )

        BrevoEmailBackend().send_messages([message])

        self.assertEqual(
            self.address_values(self.last_call_kwargs()["to"]),
            [("jose@example.test", "José Álvarez")],
        )

    def test_mapea_un_reply_to(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
            reply_to=["MotoService <taller@example.test>"],
        )

        BrevoEmailBackend().send_messages([message])

        reply_to = self.last_call_kwargs()["reply_to"]
        self.assertEqual(reply_to.email, "taller@example.test")
        self.assertEqual(reply_to.name, "MotoService")

    def test_rechaza_multiples_reply_to_sin_ignorarlos(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
            reply_to=["uno@example.test", "dos@example.test"],
        )

        with self.assertRaises(BrevoEmailMessageError):
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.brevo_send.assert_not_called()

    def test_rechaza_dos_direcciones_dentro_de_un_mismo_to(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["uno@example.test, dos@example.test"],
        )

        with self.assertRaises(BrevoEmailMessageError):
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.brevo_send.assert_not_called()

    def test_envia_multiples_mensajes_y_devuelve_la_cantidad(self):
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

        sent_count = BrevoEmailBackend().send_messages([first, second])

        self.assertEqual(sent_count, 2)
        self.assertEqual(self.brevo_send.call_count, 2)
        self.assertEqual(
            [item.kwargs["subject"] for item in self.brevo_send.call_args_list],
            ["Primero", "Segundo"],
        )
        self.assertEqual(
            [
                self.address_values(item.kwargs["to"])
                for item in self.brevo_send.call_args_list
            ],
            [
                [("uno@example.test", None)],
                [("dos@example.test", None)],
            ],
        )

    def test_propaga_error_sanitizado_cuando_fail_silently_es_false(self):
        class ErrorProveedorPrueba(Exception):
            status_code = 403
            body = {
                "code": "unauthorized",
                "message": "test-only-brevo-api-key persona@example.test",
            }

        self.brevo_send.side_effect = ErrorProveedorPrueba(
            "Contenido sensible persona@example.test"
        )
        message = EmailMessage(
            subject="Asunto",
            body="Contenido sensible",
            to=["persona@example.test"],
        )

        with self.assertRaisesMessage(
            BrevoEmailDeliveryError,
            "Email delivery through Brevo failed.",
        ) as raised:
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.assertIsNone(raised.exception.__cause__)
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertEqual(raised.exception.error_class, "ErrorProveedorPrueba")
        self.assertEqual(raised.exception.status_code, "403")
        self.assertEqual(raised.exception.provider_code, "unauthorized")
        error_message = str(raised.exception)
        self.assertNotIn("test-only-brevo-api-key", error_message)
        self.assertNotIn("Contenido sensible", error_message)
        self.assertNotIn("persona@example.test", error_message)

    def test_sanitiza_api_error_real_del_sdk(self):
        self.brevo_send.side_effect = ApiError(
            status_code=429,
            body={
                "code": "rate_limit",
                "message": "test-only-brevo-api-key persona@example.test",
            },
        )
        message = EmailMessage(
            subject="Asunto",
            body="Contenido sensible",
            to=["persona@example.test"],
        )

        with self.assertRaises(BrevoEmailDeliveryError) as raised:
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.assertEqual(raised.exception.error_class, "ApiError")
        self.assertEqual(raised.exception.status_code, "429")
        self.assertEqual(raised.exception.provider_code, "rate_limit")
        self.assertNotIn("test-only-brevo-api-key", str(raised.exception))
        self.assertNotIn("persona@example.test", str(raised.exception))

    def test_sanitiza_api_error_real_del_sdk(self):
        self.brevo_send.side_effect = ApiError(
            status_code=429,
            body={
                "code": "rate_limit",
                "message": "test-only-brevo-api-key persona@example.test",
            },
        )
        message = EmailMessage(
            subject="Asunto",
            body="Contenido sensible",
            to=["persona@example.test"],
        )

        with self.assertRaises(BrevoEmailDeliveryError) as raised:
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.assertEqual(raised.exception.error_class, "ApiError")
        self.assertEqual(raised.exception.status_code, "429")
        self.assertEqual(raised.exception.provider_code, "rate_limit")
        self.assertNotIn("test-only-brevo-api-key", str(raised.exception))
        self.assertNotIn("persona@example.test", str(raised.exception))

    def test_oculta_error_de_api_y_hace_logging_seguro(self):
        class ErrorProveedorPrueba(Exception):
            status_code = 403
            body = {
                "code": "unauthorized",
                "message": "test-only-brevo-api-key persona@example.test",
            }

        self.brevo_send.side_effect = ErrorProveedorPrueba(
            "Contenido sensible persona@example.test"
        )
        message = EmailMessage(
            subject="Asunto",
            body="Contenido sensible",
            to=["persona@example.test"],
        )

        with self.assertLogs("apps.core.email_backends", level="WARNING") as logs:
            sent_count = BrevoEmailBackend(fail_silently=True).send_messages(
                [message]
            )

        self.assertEqual(sent_count, 0)
        log_output = " ".join(logs.output)
        self.assertIn("provider=brevo", log_output)
        self.assertIn("error_class=ErrorProveedorPrueba", log_output)
        self.assertIn("status_code=403", log_output)
        self.assertIn("provider_code=unauthorized", log_output)
        self.assertNotIn("test-only-brevo-api-key", log_output)
        self.assertNotIn("Contenido sensible", log_output)
        self.assertNotIn("persona@example.test", log_output)

    def test_fail_silently_cuenta_solo_los_mensajes_realmente_enviados(self):
        class ErrorProveedorPrueba(Exception):
            status_code = 503
            body = {"code": "temporary_failure", "message": "detalle privado"}

        success = SimpleNamespace(message_id="brevo-message-test")
        self.brevo_send.side_effect = [
            success,
            ErrorProveedorPrueba("detalle privado"),
            success,
        ]
        messages = [
            EmailMessage(
                subject=f"Mensaje {number}",
                body="Contenido",
                to=[f"persona{number}@example.test"],
            )
            for number in range(1, 4)
        ]

        with self.assertLogs("apps.core.email_backends", level="WARNING"):
            sent_count = BrevoEmailBackend(fail_silently=True).send_messages(
                messages
            )

        self.assertEqual(sent_count, 2)
        self.assertEqual(self.brevo_send.call_count, 3)

    def test_rechaza_alternativa_mime_no_soportada(self):
        message = EmailMultiAlternatives(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )
        message.attach_alternative("BEGIN:VCALENDAR", "text/calendar")

        with self.assertRaisesMessage(
            BrevoEmailMessageError,
            "BrevoEmailBackend supports only text/plain and text/html content.",
        ):
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.brevo_send.assert_not_called()

    def test_omite_email_sin_destinatarios(self):
        message = EmailMessage(subject="Asunto", body="Contenido")

        sent_count = BrevoEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 0)
        self.brevo_send.assert_not_called()

    def test_rechaza_bcc_sin_destinatario_principal_sin_exponerlo(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            bcc=["oculta@example.test"],
        )

        with self.assertRaises(BrevoEmailMessageError):
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.brevo_send.assert_not_called()

    def test_rechaza_adjuntos_cuando_fail_silently_es_false(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )
        message.attach("archivo.txt", "contenido", "text/plain")

        with self.assertRaisesMessage(
            NotImplementedError,
            "Attachments are not supported by BrevoEmailBackend.",
        ):
            BrevoEmailBackend(fail_silently=False).send_messages([message])

        self.brevo_send.assert_not_called()

    def test_adjunto_falla_en_silencio_y_hace_logging_seguro(self):
        message = EmailMessage(
            subject="Asunto",
            body="Contenido",
            to=["persona@example.test"],
        )
        message.attach("secreto.txt", "contenido sensible", "text/plain")

        with self.assertLogs("apps.core.email_backends", level="WARNING") as logs:
            sent_count = BrevoEmailBackend(fail_silently=True).send_messages(
                [message]
            )

        self.assertEqual(sent_count, 0)
        self.brevo_send.assert_not_called()
        log_output = " ".join(logs.output)
        self.assertIn("NotImplementedError", log_output)
        self.assertNotIn("secreto.txt", log_output)
        self.assertNotIn("contenido sensible", log_output)

    def test_no_modifica_el_mensaje_original(self):
        message = EmailMultiAlternatives(
            subject="Asunto",
            body="Texto",
            from_email="original@example.test",
            to=["Persona <persona@example.test>"],
            cc=["Copia <copia@example.test>"],
            bcc=["Oculta <oculta@example.test>"],
            reply_to=["Respuesta <respuesta@example.test>"],
        )
        message.attach_alternative("<p>HTML</p>", "text/html")
        original_state = deepcopy(message.__dict__)

        BrevoEmailBackend().send_messages([message])

        self.assertEqual(message.__dict__, original_state)
