from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from .middleware import PrivateHtmlNoStoreMiddleware


class PrivateHtmlNoStoreMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="cache-test",
            password="clave-segura",
        )

    def assert_private_no_store(self, response):
        directivas = {
            directiva.strip().lower()
            for directiva in response.headers.get("Cache-Control", "").split(",")
        }
        self.assertIn("private", directivas)
        self.assertIn("no-store", directivas)
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")

    def test_dashboard_autenticado_no_se_almacena(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assert_private_no_store(response)

    def test_otra_vista_privada_html_no_se_almacena(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("clientes:list"))

        self.assertEqual(response.status_code, 200)
        self.assert_private_no_store(response)

    def test_login_publico_no_recibe_la_politica_privada(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

        request = RequestFactory().get(reverse("login"))
        request.user = AnonymousUser()
        request.resolver_match = resolve(request.path_info)
        respuesta_original = HttpResponse(
            "<html>login público simulado</html>",
            content_type="text/html",
        )
        middleware = PrivateHtmlNoStoreMiddleware(
            lambda _request: respuesta_original
        )

        respuesta_procesada = middleware(request)

        self.assertNotIn("Cache-Control", respuesta_procesada.headers)
        self.assertNotIn("Pragma", respuesta_procesada.headers)
        self.assertNotIn("Expires", respuesta_procesada.headers)

    def test_ruta_estatica_no_es_modificada(self):
        request = RequestFactory().get(f"{settings.STATIC_URL}css/app.css")
        request.user = self.usuario
        respuesta_original = HttpResponse(
            "<html>recurso simulado</html>",
            content_type="text/html",
        )
        middleware = PrivateHtmlNoStoreMiddleware(
            lambda _request: respuesta_original
        )

        response = middleware(request)

        self.assertNotIn("Cache-Control", response.headers)
        self.assertNotIn("Pragma", response.headers)
        self.assertNotIn("Expires", response.headers)
