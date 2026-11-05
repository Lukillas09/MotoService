import importlib.util
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


def cargar_verificador():
    ruta = settings.BASE_DIR / "scripts" / "verificar_contraste.py"
    especificacion = importlib.util.spec_from_file_location("verificar_contraste", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


class PaletaTests(SimpleTestCase):
    def test_todos_los_pares_cumplen_wcag_aa(self):
        verificador = cargar_verificador()

        fallas = [resultado for resultado in verificador.evaluar() if resultado[-1]]

        self.assertEqual(fallas, [])
        temas = {resultado[0] for resultado in verificador.evaluar()}
        self.assertEqual(temas, {"claro", "oscuro"})

    def test_cada_color_claro_tiene_valor_oscuro(self):
        verificador = cargar_verificador()
        css = (settings.BASE_DIR / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
        claro = verificador.bloque(css, ":root")
        oscuro = verificador.bloque(css, ':root[data-bs-theme="dark"]')

        colores = {
            nombre
            for nombre in claro
            if nombre.startswith(("--color-", "--surface", "--border-", "--shadow-", "--focus-", "--moto-", "--page-", "--screenshot-"))
        }
        self.assertEqual(sorted(colores - set(oscuro)), [])

    def test_el_cambio_de_tema_no_anima(self):
        css = (settings.BASE_DIR / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
        app_js = (settings.BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")

        self.assertRegex(css, r"\.theme-switching \*,[^{]*\{\s*transition: none !important;")
        self.assertIn('root.classList.add("theme-switching")', app_js)

    def test_templates_no_fijan_colores_claros_de_bootstrap(self):
        plantillas = (settings.BASE_DIR / "templates").rglob("*.html")
        prohibidas = re.compile(r'class="[^"]*\b(bg-white|text-dark|bg-light|btn-light|text-black)\b')
        for plantilla in plantillas:
            with self.subTest(plantilla=plantilla.name):
                self.assertIsNone(prohibidas.search(plantilla.read_text(encoding="utf-8")))


class TemaEnPlantillasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="mecanico", password="x")

    def test_script_de_tema_corre_antes_del_css(self):
        contenido = self.client.get(reverse("login")).content.decode("utf-8")

        script = contenido.index('localStorage.getItem("motoservice-tema")')
        primer_css = contenido.index('rel="stylesheet"')
        self.assertLess(script, primer_css)
        self.assertIn('raiz.setAttribute("data-bs-theme"', contenido)
        self.assertIn("try {", contenido)

    def test_metas_de_color_para_ambos_temas(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, '<meta name="color-scheme" content="light dark">', html=True)
        self.assertContains(response, 'content="#075ee5" media="(prefers-color-scheme: light)"')
        self.assertContains(response, 'content="#0b1220" media="(prefers-color-scheme: dark)"')

    def test_selector_en_mi_cuenta_y_en_el_menu_movil(self):
        self.client.force_login(self.usuario)

        cuenta = self.client.get(reverse("usuarios:cuenta"))
        dashboard = self.client.get(reverse("core:dashboard"))

        for valor in ("auto", "light", "dark"):
            self.assertContains(cuenta, f'id="tema-cuenta-{valor}" value="{valor}"')
            self.assertContains(cuenta, f'id="tema-menu-{valor}" value="{valor}"')
            self.assertContains(dashboard, f'id="tema-menu-{valor}" value="{valor}"')
        self.assertContains(cuenta, "data-theme-picker hidden", count=2)
        for etiqueta in ("Automático", "Claro", "Oscuro"):
            self.assertContains(cuenta, f">{etiqueta}</label>", count=2)

    def test_paginas_autocontenidas_siguen_el_tema_del_sistema(self):
        for url in ("/offline/", "/no-existe/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "@media(prefers-color-scheme:dark)", status_code=response.status_code)
                self.assertContains(response, 'content="light dark"', status_code=response.status_code)
