import json
import re
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils import timezone
from django.views.defaults import (
    bad_request,
    page_not_found,
    permission_denied,
    server_error,
)

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.servicios.models import Servicio
from config.version import APP_VERSION

from .context_processors import app_version


class VersionConfigurationTests(SimpleTestCase):
    def test_app_version_oficial(self):
        self.assertEqual(APP_VERSION, "1.0.2")

    def test_context_processor_expone_version(self):
        request = RequestFactory().get("/")

        self.assertEqual(app_version(request), {"app_version": APP_VERSION})


class VersionRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="version-test",
            password="clave-segura",
        )

    def test_dashboard_autenticado_muestra_version(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MotoService · v1.0.2", count=1)
        self.assertContains(response, 'class="app-version"', count=1)
        self.assertContains(
            response,
            'aria-label="Versión de MotoService 1.0.2"',
        )

    def test_login_publico_muestra_version(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MotoService · v1.0.2", count=1)
        self.assertContains(response, 'class="app-version"', count=1)
        self.assertContains(response, 'class="app-public')
        self.assertNotContains(response, 'class="mobile-bottom-nav"')


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )

    def test_dashboard_requiere_login(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('core:dashboard')}",
        )

    def test_dashboard_muestra_conteos_activos(self):
        activo = Cliente.objects.create(nombre="Carlos")
        Cliente.objects.create(nombre="Archivado", activo=False)
        Moto.objects.create(cliente=activo, marca="Honda", modelo="Wave")
        Moto.objects.create(
            cliente=activo, marca="Yamaha", modelo="FZ", activo=False
        )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MotoService")
        self.assertContains(response, "Clientes")
        self.assertContains(response, "Motos")
        self.assertEqual(response.context["cards"][2]["value"], 1)
        self.assertEqual(response.context["cards"][3]["value"], 1)
        self.assertTemplateUsed(response, "core/dashboard.html")

    def test_dashboard_incluye_navegacion_responsive_y_busqueda_global(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))
        contenido = response.content.decode("utf-8")

        self.assertContains(response, 'class="desktop-sidebar"')
        self.assertContains(response, 'class="mobile-bottom-nav"')
        self.assertContains(response, 'class="topbar-search"')
        self.assertGreaterEqual(contenido.count("icons/ui.svg#moto-solid"), 4)
        self.assertGreaterEqual(contenido.count("icons/ui.svg#service-gear"), 3)
        self.assertNotIn("icons/ui.svg#motorcycle", contenido)
        self.assertNotIn("icons/ui.svg#tools", contenido)
        self.assertTrue(
            (settings.BASE_DIR / "static" / "images" / "moto-generic.png").is_file()
        )
        self.assertContains(response, "icons/motoservice-mark-96.png")

    def test_busqueda_global_encuentra_clientes_y_motos(self):
        cliente = Cliente.objects.create(
            nombre="Carlos", apellido="González", telefono="260 4123456"
        )
        Moto.objects.create(
            cliente=cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
        )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:search"), {"q": "Carlos"})

        self.assertContains(response, "Carlos González")
        self.assertContains(response, "Honda Tornado")
        self.assertContains(response, 'href="tel:2604123456"')
        self.assertContains(response, 'href="https://wa.me/5492604123456"')

    def test_busqueda_global_requiere_login(self):
        response = self.client.get(reverse("core:search"), {"q": "Honda"})

        self.assertEqual(response.status_code, 302)
        destino = urlparse(response.url)
        self.assertEqual(destino.path, reverse("login"))
        self.assertEqual(parse_qs(destino.query)["next"], ["/buscar/?q=Honda"])

    def test_dashboard_muestra_solo_los_ultimos_cinco_servicios(self):
        cliente = Cliente.objects.create(nombre="Carlos")
        moto = Moto.objects.create(cliente=cliente, marca="Honda", modelo="Wave")
        servicios = [Servicio.objects.create(moto=moto) for _ in range(6)]
        MantenimientoRealizado.objects.create(
            servicio=servicios[-1],
            tipo_mantenimiento=TipoMantenimiento.objects.get(
                nombre="Cambio de aceite"
            ),
        )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(
            list(response.context["ultimos_servicios"]),
            servicios[:0:-1],
        )
        self.assertContains(response, "+ Servicio")
        self.assertContains(response, "Cambio de aceite")

    def test_dashboard_muestra_conteos_reales_y_prioriza_vencidos(self):
        aceite = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        aceite.genera_recordatorio = True
        aceite.intervalo_km = 5000
        aceite.aviso_km = 500
        aceite.save()
        cadena = TipoMantenimiento.objects.get(nombre="Cadena / transmisión")
        cadena.genera_recordatorio = True
        cadena.intervalo_km = 5000
        cadena.aviso_km = 500
        cadena.save()
        sin_registro = TipoMantenimiento.objects.get(nombre="Batería")
        sin_registro.genera_recordatorio = True
        sin_registro.intervalo_meses = 12
        sin_registro.save()
        cliente = Cliente.objects.create(nombre="Carlos")
        moto_vencida = Moto.objects.create(
            cliente=cliente,
            marca="Honda",
            modelo="Tornado",
            kilometraje_actual=20000,
        )
        moto_proxima = Moto.objects.create(
            cliente=cliente,
            marca="Yamaha",
            modelo="FZ",
            kilometraje_actual=14600,
        )
        servicio_vencido = Servicio.objects.create(
            moto=moto_vencida,
            fecha=timezone.localdate(),
            kilometraje=10000,
        )
        servicio_proximo = Servicio.objects.create(
            moto=moto_proxima,
            fecha=timezone.localdate(),
            kilometraje=10000,
        )
        MantenimientoRealizado.objects.create(
            servicio=servicio_vencido,
            tipo_mantenimiento=aceite,
        )
        MantenimientoRealizado.objects.create(
            servicio=servicio_proximo,
            tipo_mantenimiento=cadena,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.context["cards"][0]["value"], 1)
        self.assertEqual(response.context["cards"][1]["value"], 1)
        self.assertEqual(len(response.context["alertas_prioritarias"]), 2)
        self.assertEqual(
            response.context["alertas_prioritarias"][0].moto,
            moto_vencida,
        )
        self.assertContains(response, "Ver todas las alertas")

    def test_dashboard_limita_alertas_prioritarias_a_cinco(self):
        tipo = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        tipo.genera_recordatorio = True
        tipo.intervalo_km = 1000
        tipo.save()
        cliente = Cliente.objects.create(nombre="Lucía")
        for indice in range(6):
            moto = Moto.objects.create(
                cliente=cliente,
                marca="Honda",
                modelo=f"Wave {indice}",
                kilometraje_actual=3000,
            )
            servicio = Servicio.objects.create(
                moto=moto,
                fecha=timezone.localdate(),
                kilometraje=1000,
            )
            MantenimientoRealizado.objects.create(
                servicio=servicio,
                tipo_mantenimiento=tipo,
            )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.context["cards"][0]["value"], 6)
        self.assertEqual(len(response.context["alertas_prioritarias"]), 5)


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )

    def test_login_y_logout(self):
        login_response = self.client.post(
            reverse("login"),
            {"username": "mecanico", "password": "clave-segura"},
        )
        self.assertRedirects(login_response, reverse("core:dashboard"))

        logout_response = self.client.post(reverse("logout"))
        self.assertRedirects(logout_response, reverse("login"))

    def test_login_es_publico_y_admin_sigue_disponible(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="login-shell"')
        self.assertContains(response, "icons/motoservice-mark-96.png")
        self.assertContains(response, "icons/favicon-32.png")
        self.assertNotContains(response, 'class="desktop-sidebar"')
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_login_rechaza_redireccion_externa(self):
        response = self.client.post(
            f'{reverse("login")}?next=https://example.com/salida',
            {"username": "mecanico", "password": "clave-segura"},
        )

        self.assertRedirects(response, reverse("core:dashboard"))


class ProductionReadinessTests(TestCase):
    def test_urls_compartidas_de_mantenimientos_resuelven_sin_colisiones(self):
        casos = {
            "/mantenimientos/": "notificaciones:alertas",
            "/mantenimientos/1/2/contactar/": "notificaciones:contactar",
            "/mantenimientos/configuracion/": "mantenimientos:configuracion",
            "/mantenimientos/configuracion/nuevo/": "mantenimientos:tipo_create",
        }

        for ruta, vista_esperada in casos.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(resolve(ruta).view_name, vista_esperada)

    def test_configuracion_de_tests_usa_solo_la_url_de_tests_opcional(self):
        if settings.TEST_DATABASE_URL:
            self.assertEqual(
                settings.DATABASES["default"]["ENGINE"],
                "django.db.backends.postgresql",
            )
        else:
            self.assertEqual(
                settings.DATABASES["default"]["ENGINE"],
                "django.db.backends.sqlite3",
            )
            self.assertIn("memory", str(settings.DATABASES["default"]["NAME"]))

    def test_staticfiles_de_tests_no_requiere_manifiesto_de_produccion(self):
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )
        self.assertFalse(hasattr(settings, "STATICFILES_STORAGE"))

    def test_manifest_pwa_es_valido_y_sus_iconos_existen(self):
        manifest_path = settings.BASE_DIR / "static" / "manifest.webmanifest"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertTrue(manifest["icons"])
        for icono in manifest["icons"]:
            ruta_relativa = icono["src"].removeprefix("/static/")
            self.assertTrue((settings.BASE_DIR / "static" / ruta_relativa).is_file())

        iconos_png = [
            icono for icono in manifest["icons"] if icono["type"] == "image/png"
        ]
        self.assertIn("192x192", {icono["sizes"] for icono in iconos_png})
        self.assertIn("512x512", {icono["sizes"] for icono in iconos_png})
        self.assertIn(
            "/static/icons/icon-512.png",
            {icono["src"] for icono in iconos_png},
        )
        self.assertEqual(
            {
                (icono["src"], icono["sizes"], icono["purpose"])
                for icono in iconos_png
            },
            {
                ("/static/icons/icon-192.png", "192x192", "any"),
                ("/static/icons/icon-512.png", "512x512", "any"),
                ("/static/icons/icon-maskable-192.png", "192x192", "maskable"),
                ("/static/icons/icon-maskable-512.png", "512x512", "maskable"),
            },
        )
        for icono in iconos_png:
            dimensiones = icono["sizes"]
            ruta = settings.BASE_DIR / "static" / icono["src"].removeprefix(
                "/static/"
            )
            contenido = ruta.read_bytes()
            self.assertEqual(contenido[:8], b"\x89PNG\r\n\x1a\n")
            ancho = int.from_bytes(contenido[16:20], "big")
            alto = int.from_bytes(contenido[20:24], "big")
            esperado = int(dimensiones.split("x", maxsplit=1)[0])
            self.assertEqual((ancho, alto), (esperado, esperado))

        apple_icon = settings.BASE_DIR / "static" / "icons" / "apple-touch-icon.png"
        self.assertTrue(apple_icon.is_file())
        apple_data = apple_icon.read_bytes()
        self.assertEqual(
            (
                int.from_bytes(apple_data[16:20], "big"),
                int.from_bytes(apple_data[20:24], "big"),
            ),
            (180, 180),
        )

        favicon = settings.BASE_DIR / "static" / "icons" / "favicon-32.png"
        favicon_data = favicon.read_bytes()
        self.assertEqual(favicon_data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(
            (
                int.from_bytes(favicon_data[16:20], "big"),
                int.from_bytes(favicon_data[20:24], "big"),
            ),
            (32, 32),
        )

    def test_assets_de_identidad_son_locales_optimizados_y_reutilizables(self):
        static_dir = settings.BASE_DIR / "static"
        assets = {
            "master": static_dir / "icons" / "motoservice-mark.png",
            "interfaz": static_dir / "icons" / "motoservice-mark-96.png",
            "moto": static_dir / "images" / "moto-generic.png",
            "sprite": static_dir / "icons" / "ui.svg",
        }
        for asset in assets.values():
            self.assertTrue(asset.is_file(), asset)

        for nombre, dimensiones in {
            "master": (1024, 1024),
            "interfaz": (96, 96),
            "moto": (1200, 668),
        }.items():
            contenido = assets[nombre].read_bytes()
            self.assertEqual(contenido[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(
                (
                    int.from_bytes(contenido[16:20], "big"),
                    int.from_bytes(contenido[20:24], "big"),
                ),
                dimensiones,
            )

        self.assertLess(assets["master"].stat().st_size, 1_000_000)
        self.assertLess(assets["moto"].stat().st_size, 1_000_000)
        sprite = assets["sprite"].read_text(encoding="utf-8")
        self.assertIn('id="moto-solid"', sprite)
        self.assertIn('id="service-gear"', sprite)
        self.assertNotIn('id="motorcycle"', sprite)
        self.assertNotIn('id="tools"', sprite)
        for symbol_id in ("moto-solid", "service-gear"):
            self.assertIn(
                f'<symbol id="{symbol_id}" viewBox="0 0 24 24" '
                'fill="currentColor" stroke="none">',
                sprite,
            )

    def test_service_worker_se_sirve_desde_raiz_y_solo_cachea_estaticos(self):
        response = self.client.get(reverse("service-worker"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["Content-Type"])
        contenido = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn('url.pathname.startsWith("/static/")', contenido)
        self.assertIn('event.request.method !== "GET"', contenido)
        self.assertIn("url.origin !== self.location.origin", contenido)
        self.assertIn('const CACHE_NAME = "motoservice-static-v13"', contenido)
        for asset in (
            "/static/icons/ui.svg",
            "/static/js/guide.js",
            "/static/icons/motoservice-mark-96.png",
            "/static/icons/favicon-32.png",
            "/static/images/moto-generic.png",
            "/static/icons/icon-maskable-192.png",
            "/static/icons/icon-maskable-512.png",
        ):
            self.assertIn(asset, contenido)
        self.assertNotIn("moto-generic.svg", contenido)
        self.assertNotIn("icons/icon.svg", contenido)
        for ruta_privada in (
            "/clientes/",
            "/motos/",
            "/exportaciones/",
            "/guia/",
            "/usuarios/",
            "/cuenta/",
            "/accounts/password-reset/",
        ):
            self.assertNotIn(ruta_privada, contenido)

    def test_css_declara_tokens_y_respeta_reduccion_de_movimiento(self):
        css = (settings.BASE_DIR / "static" / "css" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("--color-primary", css)
        self.assertIn("--surface", css)
        self.assertIn("--radius-lg", css)
        self.assertIn("--shadow-md", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

    def test_badge_de_version_permanece_en_el_flujo_del_layout(self):
        css = (settings.BASE_DIR / "static" / "css" / "app.css").read_text(
            encoding="utf-8"
        )
        reglas_version = [
            coincidencia.group("declaraciones")
            for coincidencia in re.finditer(
                r"(?P<selectores>[^{}]+)\{(?P<declaraciones>[^{}]*)\}",
                css,
            )
            if re.search(
                r"(?<![\w-])\.app-version(?![\w-])",
                coincidencia.group("selectores"),
            )
        ]

        self.assertTrue(reglas_version)
        self.assertRegex(
            "\n".join(reglas_version),
            r"(?i)\balign-self\s*:\s*flex-end\b",
        )
        for declaraciones in reglas_version:
            with self.subTest(declaraciones=declaraciones.strip()):
                self.assertNotRegex(
                    declaraciones,
                    r"(?i)\bposition\s*:\s*(?:absolute|fixed|sticky|-webkit-sticky)\b",
                )

        cuerpo = re.search(r"(?m)^body\s*\{(?P<declaraciones>[^}]*)\}", css)
        app_main = re.search(r"(?m)^\.app-main\s*\{(?P<declaraciones>[^}]*)\}", css)
        contenido_publico = re.search(
            r"(?m)^\.public-content\s*\{(?P<declaraciones>[^}]*)\}", css
        )
        self.assertIsNotNone(cuerpo)
        self.assertIsNotNone(app_main)
        self.assertIsNotNone(contenido_publico)
        self.assertRegex(cuerpo.group("declaraciones"), r"\bdisplay\s*:\s*flex\b")
        self.assertRegex(
            cuerpo.group("declaraciones"), r"\bflex-direction\s*:\s*column\b"
        )
        for contenedor in (app_main, contenido_publico):
            self.assertRegex(
                contenedor.group("declaraciones"),
                r"\bflex\s*:\s*1\s+0\s+auto\b",
            )

        inicio_mobile = css.index("@media (max-width: 991.98px)")
        fin_mobile = css.index("@media (max-width: 767.98px)", inicio_mobile)
        css_mobile = css[inicio_mobile:fin_mobile]
        reserva = re.search(
            r"body\.app-authenticated\s*\{[^}]*padding-bottom:\s*"
            r"calc\(\s*(?P<rem>[\d.]+)rem\s*\+\s*"
            r"env\(safe-area-inset-bottom\)\s*\)",
            css_mobile,
        )
        navegacion = re.search(
            r"\.mobile-bottom-nav\s*\{[^}]*height:\s*"
            r"calc\(\s*(?P<rem>[\d.]+)rem\s*\+\s*"
            r"env\(safe-area-inset-bottom\)\s*\)",
            css_mobile,
        )
        self.assertIsNotNone(reserva)
        self.assertIsNotNone(navegacion)
        self.assertGreaterEqual(
            float(reserva.group("rem")),
            float(navegacion.group("rem")),
        )

    def test_paginas_de_error_no_exponen_detalles_tecnicos(self):
        request = RequestFactory().get("/ruta-inexistente/")
        detalle_sensible = "detalle-interno-no-visible"
        respuestas = [
            bad_request(request, Exception(detalle_sensible)),
            permission_denied(request, Exception(detalle_sensible)),
            page_not_found(request, Exception(detalle_sensible)),
            server_error(request),
        ]

        for respuesta, codigo in zip(respuestas, (400, 403, 404, 500), strict=True):
            with self.subTest(codigo=codigo):
                contenido = respuesta.content.decode("utf-8")
                self.assertEqual(respuesta.status_code, codigo)
                self.assertIn(f"ERROR {codigo}", contenido)
                self.assertIn("icons/motoservice-mark-96.png", contenido)
                self.assertIn("icons/favicon-32.png", contenido)
                self.assertNotIn(detalle_sensible, contenido)
