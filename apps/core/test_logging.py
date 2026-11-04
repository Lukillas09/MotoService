import logging
import os
import re
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path

from config.settings.base import construir_logging, env_log_level


def vista_que_falla(request):
    raise RuntimeError("fallo de prueba")


urlpatterns = [path("falla/", vista_que_falla)]


class LoggingConfigTests(SimpleTestCase):
    def test_consola_escribe_a_stdout_con_timestamp_nivel_logger_y_mensaje(self):
        configuracion = construir_logging("INFO")
        handler = configuracion["handlers"]["console"]
        formato = configuracion["formatters"][handler["formatter"]]
        registro = logging.LogRecord(
            "apps.core", logging.WARNING, __file__, 1, "mensaje de prueba", (), None
        )

        salida = logging.Formatter(formato["format"], style=formato["style"]).format(
            registro
        )

        self.assertEqual(handler["stream"], "ext://sys.stdout")
        self.assertRegex(
            salida,
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} WARNING apps\.core mensaje de prueba$",
        )

    def test_request_y_security_nunca_bajan_de_warning(self):
        for nivel, esperado in (
            ("DEBUG", "WARNING"),
            ("INFO", "WARNING"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
        ):
            with self.subTest(nivel=nivel):
                loggers = construir_logging(nivel)["loggers"]
                self.assertEqual(loggers["django.request"]["level"], esperado)
                self.assertEqual(loggers["django.security"]["level"], esperado)
                self.assertEqual(loggers["apps"]["level"], nivel)

    def test_log_level_tiene_default_y_rechaza_valores_invalidos(self):
        with patch.dict(os.environ, {"LOG_LEVEL_PRUEBA": " debug "}):
            self.assertEqual(env_log_level("LOG_LEVEL_PRUEBA", "INFO"), "DEBUG")
        with patch.dict(os.environ, {"LOG_LEVEL_PRUEBA": ""}):
            self.assertEqual(env_log_level("LOG_LEVEL_PRUEBA", "INFO"), "INFO")
        with patch.dict(os.environ, {"LOG_LEVEL_PRUEBA": "verbose"}):
            with self.assertRaises(ImproperlyConfigured):
                env_log_level("LOG_LEVEL_PRUEBA", "INFO")

    def test_tests_usan_warning_por_defecto_sin_imprimir(self):
        if os.getenv("LOG_LEVEL"):
            self.skipTest("LOG_LEVEL está definido en el entorno.")
        self.assertEqual(settings.LOG_LEVEL, "WARNING")
        self.assertEqual(
            settings.LOGGING["handlers"]["console"]["class"], "logging.NullHandler"
        )


@override_settings(ROOT_URLCONF=__name__)
class ErrorServidorLoggingTests(SimpleTestCase):
    def test_error_500_queda_registrado_en_django_request(self):
        cliente = Client(raise_request_exception=False)

        with self.assertLogs("django.request", level="ERROR") as logs:
            response = cliente.get("/falla/?telefono=2604123456")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(logs.records), 1)
        registro = logs.records[0]
        self.assertEqual(registro.levelname, "ERROR")
        self.assertTrue(re.search(r"Internal Server Error: /falla/$", registro.getMessage()))
        # Django registra la ruta, nunca la query string con datos del cliente.
        self.assertNotIn("2604123456", registro.getMessage())
