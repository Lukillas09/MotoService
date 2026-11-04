from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.usuarios.models import LimiteAutenticacion


class HealthzTests(TestCase):
    url = "/healthz/"

    def test_ruta_publica_esperada_por_railway(self):
        self.assertEqual(reverse("core:healthz"), self.url)

    def test_responde_200_sin_login_sesion_ni_cache(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.cookies, {})
        self.assertNotIn("Cookie", response.get("Vary", ""))

    def test_responde_503_sin_detalles_si_la_base_no_responde(self):
        with (
            patch("apps.core.views.connection") as conexion,
            self.assertLogs("apps.core.views", level="WARNING") as logs,
        ):
            conexion.cursor.side_effect = OperationalError(
                'connection to server at "db.secreto.supabase.co" failed'
            )
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error", "database": "unavailable"})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotContains(response, "supabase", status_code=503)
        log_output = " ".join(logs.output)
        self.assertIn("error_type=OperationalError", log_output)
        self.assertNotIn("supabase", log_output)

    def test_solo_acepta_lecturas(self):
        self.assertEqual(self.client.head(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_no_pasa_por_el_rate_limiting(self):
        for _ in range(30):
            self.assertEqual(self.client.get(self.url).status_code, 200)

        self.assertFalse(LimiteAutenticacion.objects.exists())

    @override_settings(
        ALLOWED_HOSTS=["motoservice.example.test", "healthcheck.railway.app"],
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^healthz/$"],
    )
    def test_healthcheck_interno_por_http_no_se_redirige_a_https(self):
        interno = self.client.get(self.url, HTTP_HOST="healthcheck.railway.app")
        privada = self.client.get(
            reverse("clientes:list"), HTTP_HOST="motoservice.example.test"
        )

        self.assertEqual(interno.status_code, 200)
        self.assertEqual(privada.status_code, 301)
        self.assertTrue(privada["Location"].startswith("https://"))
