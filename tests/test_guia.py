from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from apps.core.guia import CAPTURAS, TEMAS
from apps.usuarios.roles import GRUPO_PROPIETARIO


TEMAS_USUARIO = tuple(tema for tema in TEMAS if tema["slug"] != "exportaciones")


class GuiaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="lector-guia")
        cls.propietario = get_user_model().objects.create_user(
            username="propietario-guia"
        )
        cls.propietario.groups.add(
            Group.objects.create(name=GRUPO_PROPIETARIO)
        )
        cls.superuser = get_user_model().objects.create_superuser(
            username="superuser-guia"
        )

    def test_todas_las_rutas_requieren_login(self):
        rutas = [reverse("core:guia")] + [
            reverse("core:guia_tema", args=[tema["slug"]]) for tema in TEMAS
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertRedirects(
                    self.client.get(ruta), f"{reverse('login')}?next={ruta}"
                )

    def test_portada_usuario_oculta_categoria_exportaciones(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:guia"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "guia/index.html")
        self.assertContains(response, 'for="guide-search"')
        self.assertContains(
            response,
            'data-guide-keywords=',
            count=len(TEMAS_USUARIO),
        )
        for tema in TEMAS_USUARIO:
            self.assertContains(
                response,
                reverse("core:guia_tema", args=[tema["slug"]]),
            )
        self.assertNotContains(
            response,
            reverse("core:guia_tema", args=["exportaciones"]),
        )

    def test_portada_propietario_y_superuser_muestra_exportaciones(self):
        for usuario in (self.propietario, self.superuser):
            self.client.force_login(usuario)
            response = self.client.get(reverse("core:guia"))

            with self.subTest(usuario=usuario.username):
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    'data-guide-keywords=',
                    count=len(TEMAS),
                )
                self.assertContains(
                    response,
                    reverse("core:guia_tema", args=["exportaciones"]),
                )

    def test_categorias_y_enlace_de_regreso(self):
        self.client.force_login(self.usuario)
        for tema in TEMAS_USUARIO:
            with self.subTest(tema=tema["slug"]):
                response = self.client.get(
                    reverse("core:guia_tema", args=[tema["slug"]])
                )
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response,
                    f"guia/temas/{tema['slug']}.html",
                )
                self.assertContains(response, 'href="/guia/"')
                self.assertNotContains(response, 'href="/" aria-current="page"')

    def test_tema_exportaciones_respeta_el_rol(self):
        url = reverse("core:guia_tema", args=["exportaciones"])
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(url).status_code, 403)

        for usuario in (self.propietario, self.superuser):
            self.client.force_login(usuario)
            with self.subTest(usuario=usuario.username):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response,
                    "guia/temas/exportaciones.html",
                )

    def test_guia_usuario_no_muestra_enlaces_hacia_exportaciones(self):
        self.client.force_login(self.usuario)
        enlaces_restringidos = (
            f'href="{reverse("core:guia_tema", args=["exportaciones"])}',
            f'href="{reverse("exportaciones:index")}',
        )

        for tema in TEMAS_USUARIO:
            with self.subTest(tema=tema["slug"]):
                response = self.client.get(
                    reverse("core:guia_tema", args=[tema["slug"]])
                )
                for enlace in enlaces_restringidos:
                    self.assertNotContains(response, enlace)

    def test_tema_desconocido_es_404(self):
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.get("/guia/tema-inexistente/").status_code,
            404,
        )

    def test_guia_en_navegacion_desktop_y_mobile(self):
        self.client.force_login(self.usuario)
        contenido = self.client.get(reverse("core:dashboard")).content.decode()
        sidebar = contenido.split('<nav class="sidebar-nav">')[1].split('</nav>')[0]
        mobile = contenido.split('<nav class="mobile-more-nav">')[1].split(
            "</nav>"
        )[0]
        for nav in (sidebar, mobile):
            self.assertIn('href="/guia/"', nav)
            self.assertIn('Guía de uso', nav)

    def test_enlaces_contextuales_apuntan_a_secciones_existentes(self):
        self.client.force_login(self.propietario)
        for origen, tema, anchor in (
            ("mantenimientos:configuracion", "mantenimientos", "reglas"),
            ("notificaciones:alertas", "seguimiento", "estados"),
            ("exportaciones:index", "exportaciones", "backup"),
        ):
            with self.subTest(origen=origen):
                destino = reverse("core:guia_tema", args=[tema])
                self.assertContains(
                    self.client.get(reverse(origen)),
                    f'href="{destino}#{anchor}"',
                )
                self.assertContains(self.client.get(destino), f'id="{anchor}"')

    def test_capturas_reales_se_cargan_solo_en_su_tutorial(self):
        self.client.force_login(self.usuario)
        for clave, (archivo, _alt) in CAPTURAS.items():
            if clave == "ios":
                continue
            with self.subTest(captura=archivo):
                self.assertIsNotNone(finders.find(f"guide/{archivo}"))

        primeros_pasos = self.client.get(
            reverse("core:guia_tema", args=["primeros-pasos"])
        )
        self.assertContains(primeros_pasos, "guide/01-dashboard.webp")
        self.assertContains(primeros_pasos, 'loading="lazy"')

        instalar = self.client.get(reverse("core:guia_tema", args=["instalar"]))
        self.assertNotContains(instalar, "guide-screenshot")

    @patch("apps.core.views.finders.find", return_value=None)
    def test_capturas_ausentes_no_generan_imagenes_rotas(self, _find):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:guia_tema", args=["clientes"]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "guide-screenshot")
        self.assertContains(response, "guide-step")

    def test_faq_tiene_controles_y_respuestas_sin_js(self):
        self.client.force_login(self.usuario)
        response = self.client.get(
            reverse("core:guia_tema", args=["preguntas-frecuentes"])
        )
        self.assertContains(response, 'data-bs-toggle="collapse"', count=12)
        self.assertContains(response, 'aria-controls="respuesta-whatsapp"')
        self.assertContains(response, '<noscript>')
        self.assertContains(response, 'id="respuesta-whatsapp"')

        self.client.force_login(self.propietario)
        response = self.client.get(
            reverse("core:guia_tema", args=["preguntas-frecuentes"])
        )
        self.assertContains(response, 'data-bs-toggle="collapse"', count=13)
        self.assertContains(response, 'id="respuesta-descargar"')

    def test_clientes_explica_contacto_rapido_sin_seguimiento_automatico(self):
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse("core:guia_tema", args=["clientes"])
        )

        self.assertContains(response, 'id="contacto-rapido"')
        self.assertContains(response, "Elegí Llamar o WhatsApp")
        self.assertContains(
            response,
            "no marca automáticamente al cliente como contactado",
        )
