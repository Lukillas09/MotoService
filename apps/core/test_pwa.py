import json
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.core import pwa
from config.version import APP_VERSION


def static_con_hash(ruta):
    """Simula ManifestStaticFilesStorage: tokens.css -> tokens.3f9a1c.css."""
    base, punto, extension = ruta.rpartition(".")
    return f"/static/{base}.3f9a1c{punto}{extension}"


class ServiceWorkerTests(TestCase):
    url = "/service-worker.js"

    def setUp(self):
        pwa._datos_en_produccion = None
        self.addCleanup(setattr, pwa, "_datos_en_produccion", None)

    def contenido(self, response):
        return response.content.decode("utf-8")

    def recursos(self, response):
        coincidencia = re.search(r"const STATIC_ASSETS = (\[.*?\]);", self.contenido(response))
        return json.loads(coincidencia.group(1))

    def test_se_sirve_en_la_raiz_como_javascript_sin_cache_ni_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"], "application/javascript; charset=utf-8"
        )
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response.cookies, {})

    def test_usuario_autenticado_recibe_el_mismo_js_sin_politica_privada(self):
        usuario = get_user_model().objects.create_user(username="mecanico", password="x")
        self.client.force_login(usuario)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertNotIn("Pragma", response)

    def test_precarga_las_urls_con_hash_del_manifest(self):
        with patch("apps.core.pwa.static", side_effect=static_con_hash):
            response = self.client.get(self.url)

        recursos = self.recursos(response)
        self.assertIn("/static/css/tokens.3f9a1c.css", recursos)
        self.assertIn("/static/css/utilities.3f9a1c.css", recursos)
        self.assertIn("/static/js/app.3f9a1c.js", recursos)
        self.assertIn("/static/icons/motoservice-mark-96.3f9a1c.png", recursos)
        self.assertNotIn("/static/css/tokens.css", recursos)
        self.assertEqual(len(recursos), len(pwa.RECURSOS_PRECARGADOS))
        self.assertIn('const OFFLINE_URL = "/offline/"', self.contenido(response))

    def test_todos_los_recursos_precargados_existen(self):
        from django.contrib.staticfiles import finders

        for ruta in pwa.RECURSOS_PRECARGADOS:
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(finders.find(ruta))

    def test_nombre_de_cache_deriva_de_version_y_contenido(self):
        primera = self.contenido(self.client.get(self.url))
        nombre = re.search(r'const CACHE_NAME = "([^"]+)"', primera).group(1)

        self.assertRegex(nombre, rf"^motoservice-{re.escape(APP_VERSION)}-[0-9a-f]{{12}}$")
        self.assertEqual(self.contenido(self.client.get(self.url)), primera)

        pwa._datos_en_produccion = None
        with patch("apps.core.pwa.static", side_effect=static_con_hash):
            con_hash = self.contenido(self.client.get(self.url))
        self.assertNotIn(nombre, con_hash)

    @override_settings(DEBUG=False)
    def test_en_produccion_se_calcula_una_vez_por_proceso(self):
        with patch("apps.core.pwa._calcular_datos", wraps=pwa._calcular_datos) as calculo:
            self.client.get(self.url)
            self.client.get(self.url)

        self.assertEqual(calculo.call_count, 1)

    def test_estrategia_no_cachea_html_privado_ni_htmx(self):
        contenido = self.contenido(self.client.get(self.url))

        self.assertIn('if (request.method !== "GET") return;', contenido)
        self.assertIn("if (url.origin !== self.location.origin) return;", contenido)
        self.assertIn('request.mode === "navigate"', contenido)
        self.assertIn("fetch(request).catch(() =>", contenido)
        self.assertIn("caches.match(OFFLINE_URL)", contenido)
        self.assertIn("if (!url.pathname.startsWith(STATIC_PREFIX)) return;", contenido)
        self.assertIn('const STATIC_PREFIX = "/static/";', contenido)
        # El único cache.put/addAll es la precarga de install.
        self.assertEqual(contenido.count("cache.addAll"), 1)
        self.assertNotIn("cache.put", contenido)
        for ruta_privada in (
            "/clientes/",
            "/motos/",
            "/exportaciones/",
            "/guia/",
            "/usuarios/",
            "/cuenta/",
            "/accounts/",
        ):
            self.assertNotIn(ruta_privada, contenido)

    def test_activate_borra_cachés_viejas(self):
        contenido = self.contenido(self.client.get(self.url))

        self.assertIn("keys.filter((key) => key !== CACHE_NAME)", contenido)
        self.assertIn("caches.delete(key)", contenido)


class PaginaOfflineTests(TestCase):
    def test_es_publica_autocontenida_y_tiene_reintentar(self):
        response = self.client.get("/offline/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertContains(response, "No hay conexión a internet")
        self.assertContains(response, '<a href="">Reintentar</a>', html=True)
        self.assertContains(response, "MotoService")
        self.assertNotContains(response, "<script")
        self.assertNotContains(response, 'rel="stylesheet"')

    def test_no_incluye_datos_de_la_sesion(self):
        usuario = get_user_model().objects.create_user(
            username="mecanico", password="x", first_name="Carla"
        )
        self.client.force_login(usuario)

        response = self.client.get("/offline/")

        self.assertNotContains(response, "mecanico")
        self.assertNotContains(response, "Carla")
        self.assertNotContains(response, "csrfmiddlewaretoken")
        self.assertNotIn("private", response["Cache-Control"])
