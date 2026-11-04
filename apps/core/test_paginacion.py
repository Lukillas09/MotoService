from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
import warnings

from django.contrib.auth import get_user_model
from django.core.paginator import UnorderedObjectListWarning
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.servicios.models import Servicio


def _ids_de_todas_las_paginas(
    client, url, nombre_contexto, parametros=None, clave=lambda objeto: objeto.pk
):
    ids = []
    numero = 1
    while True:
        response = client.get(url, {**(parametros or {}), "page": numero})
        pagina = response.context["page_obj"]
        ids.extend(clave(objeto) for objeto in response.context[nombre_contexto])
        if not pagina.has_next():
            return ids, pagina.paginator.count
        numero += 1


class OrdenDeterministicoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )

    def test_ningun_listado_pagina_un_queryset_sin_orden(self):
        self.client.force_login(self.usuario)
        for nombre in ("clientes:list", "motos:list", "servicios:list"):
            for parametros in ({}, {"q": "26"}):
                with self.subTest(url=nombre, parametros=parametros):
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", UnorderedObjectListWarning)
                        response = self.client.get(reverse(nombre), parametros)
                    self.assertEqual(response.status_code, 200)


class UrlPaginaTagTests(SimpleTestCase):
    def renderizar(self, consulta, numero):
        request = RequestFactory().get(f"/clientes/?{consulta}")
        template = Template("{% load paginacion %}{% url_pagina numero %}")
        return template.render(Context({"request": request, "numero": numero}))

    def test_conserva_filtros_y_reemplaza_la_pagina(self):
        url = self.renderizar("q=gomez&estado=archivados&page=4", 2)

        consulta = parse_qs(urlsplit(url.replace("&amp;", "&")).query)
        self.assertEqual(consulta, {"q": ["gomez"], "estado": ["archivados"], "page": ["2"]})

    def test_pagina_uno_omite_el_parametro(self):
        self.assertEqual(self.renderizar("q=gomez&page=3", 1), "/clientes/?q=gomez")
        self.assertEqual(self.renderizar("page=3", 1), "/clientes/")


@override_settings(LISTADO_POR_PAGINA=2)
class PaginacionClientesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )
        # Mismos apellido y nombre para forzar el desempate por pk.
        for _ in range(4):
            Cliente.objects.create(nombre="Ana", apellido="Gomez")
        Cliente.objects.create(nombre="Beto", apellido="Zárate")
        for numero in range(3):
            Cliente.objects.create(nombre=f"Archivado {numero}", apellido="Gomez", activo=False)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_primera_pagina_muestra_limite_y_resumen(self):
        response = self.client.get(reverse("clientes:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["clientes"]), 2)
        self.assertContains(response, "Mostrando 1–2 de 5")
        self.assertContains(response, 'aria-label="Páginas de clientes"')
        self.assertContains(
            response, 'aria-label="Página 1" aria-current="page"', count=1
        )
        self.assertContains(response, 'href="/clientes/?page=2"')

    def test_recorrer_todas_las_paginas_no_duplica_ni_saltea_filas(self):
        ids, total = _ids_de_todas_las_paginas(
            self.client, reverse("clientes:list"), "clientes"
        )

        esperados = list(
            Cliente.objects.filter(activo=True).values_list("pk", flat=True)
        )
        self.assertEqual(total, 5)
        self.assertEqual(ids, esperados)

    def test_conserva_busqueda_y_estado_al_cambiar_de_pagina(self):
        response = self.client.get(
            reverse("clientes:list"),
            {"q": "gomez", "estado": "archivados", "page": 2},
        )

        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(response.context["page_obj"].paginator.count, 3)
        self.assertTrue(all(not cliente.activo for cliente in response.context["clientes"]))
        self.assertContains(response, 'href="/clientes/?q=gomez&amp;estado=archivados"')

    def test_buscar_o_cambiar_estado_vuelve_a_la_pagina_uno(self):
        response = self.client.get(reverse("clientes:list"), {"page": 2})

        # Ni el formulario de búsqueda ni las pestañas de estado arrastran la página.
        self.assertNotContains(response, 'name="page"')
        self.assertContains(response, 'href="/clientes/?estado=archivados"')

    def test_pagina_invalida_o_fuera_de_rango_no_falla(self):
        for valor, esperada in (("abc", 1), ("0", 3), ("999", 3), ("", 1)):
            with self.subTest(page=valor):
                response = self.client.get(reverse("clientes:list"), {"page": valor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["page_obj"].number, esperada)

    def test_htmx_devuelve_solo_resultados_con_paginacion_parcial(self):
        response = self.client.get(
            reverse("clientes:list"),
            {"q": "gomez", "page": 2},
            HTTP_HX_REQUEST="true",
        )

        self.assertNotContains(response, "<html")
        self.assertTemplateUsed(response, "shared/paginacion.html")
        self.assertContains(response, 'hx-target="#clientes-results"')
        self.assertContains(response, 'hx-push-url="true"')
        self.assertContains(response, 'hx-get="/clientes/?q=gomez"')
        self.assertContains(response, "Mostrando 3–4 de 4")

    def test_sin_resultados_no_muestra_paginacion(self):
        response = self.client.get(reverse("clientes:list"), {"q": "inexistente"})

        self.assertContains(response, "No encontramos clientes")
        self.assertNotContains(response, "pagination-bar")


@override_settings(LISTADO_POR_PAGINA=2)
class PaginacionMotosServiciosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )
        cliente = Cliente.objects.create(nombre="Carlos", apellido="López")
        hoy = timezone.localdate()
        for numero in range(5):
            moto = Moto.objects.create(cliente=cliente, marca="Honda", modelo="Wave")
            # Dos servicios por moto el mismo día: el orden depende del pk.
            Servicio.objects.create(moto=moto, fecha=hoy, kilometraje=numero)
            Servicio.objects.create(
                moto=moto,
                fecha=hoy,
                estado=Servicio.Estado.ABIERTO,
            )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_motos_paginan_con_orden_estable(self):
        ids, total = _ids_de_todas_las_paginas(
            self.client, reverse("motos:list"), "motos"
        )

        self.assertEqual(total, 5)
        self.assertEqual(ids, list(Moto.objects.values_list("pk", flat=True)))

    def test_motos_htmx_reemplaza_solo_sus_resultados(self):
        response = self.client.get(
            reverse("motos:list"), {"page": 2}, HTTP_HX_REQUEST="true"
        )

        self.assertNotContains(response, "<html")
        self.assertContains(response, 'hx-target="#motos-results"')

    def test_servicios_paginan_con_orden_estable(self):
        ids, total = _ids_de_todas_las_paginas(
            self.client, reverse("servicios:list"), "servicios"
        )

        self.assertEqual(total, 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, list(Servicio.objects.values_list("pk", flat=True)))

    def test_servicios_conservan_filtros_entre_paginas(self):
        parametros = {"q": "honda", "estado": Servicio.Estado.ABIERTO}

        ids, total = _ids_de_todas_las_paginas(
            self.client, reverse("servicios:list"), "servicios", parametros
        )
        response = self.client.get(
            reverse("servicios:list"), {**parametros, "page": 2}
        )

        self.assertEqual(total, 5)
        self.assertEqual(
            set(ids),
            set(
                Servicio.objects.filter(
                    estado=Servicio.Estado.ABIERTO
                ).values_list("pk", flat=True)
            ),
        )
        self.assertContains(
            response, 'href="/servicios/?q=honda&amp;estado=ABIERTO&amp;page=3"'
        )
        self.assertContains(response, 'hx-target="#servicios-resultados"')


@override_settings(LISTADO_POR_PAGINA=2)
class PaginacionAlertasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )
        tipo = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        tipo.activo = True
        tipo.genera_recordatorio = True
        tipo.intervalo_meses = None
        tipo.intervalo_km = 5000
        tipo.aviso_km = 500
        tipo.save()
        cliente = Cliente.objects.create(nombre="Carlos", apellido="López")
        for numero in range(5):
            moto = Moto.objects.create(
                cliente=cliente,
                marca="Honda",
                modelo=f"Wave {numero}",
                kilometraje_actual=20000,
            )
            servicio = Servicio.objects.create(
                moto=moto,
                fecha=timezone.localdate() - timedelta(days=30),
                kilometraje=10000,
            )
            MantenimientoRealizado.objects.create(
                servicio=servicio,
                tipo_mantenimiento=tipo,
            )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_paginar_no_cambia_conteos_del_encabezado_ni_del_dashboard(self):
        primera = self.client.get(reverse("notificaciones:alertas"))
        ultima = self.client.get(reverse("notificaciones:alertas"), {"page": 3})
        dashboard = self.client.get(reverse("core:dashboard"))

        self.assertEqual(len(primera.context["alertas"]), 2)
        self.assertEqual(len(ultima.context["alertas"]), 1)
        for response in (primera, ultima):
            self.assertEqual(response.context["page_obj"].paginator.count, 5)
            self.assertEqual(len(response.context["resumen"].alertas), 5)
            self.assertEqual(len(response.context["resumen"].vencidos), 5)
            self.assertContains(
                response,
                'Vencidos <span class="filter-chip-count">5</span>',
            )
        self.assertEqual(dashboard.context["cards"][0]["value"], 5)

    def test_recorrer_alertas_mantiene_el_orden_de_urgencia(self):
        ids, total = _ids_de_todas_las_paginas(
            self.client,
            reverse("notificaciones:alertas"),
            "alertas",
            {"estado": "VENCIDO", "seguimiento": "todos"},
            clave=lambda alerta: alerta.alerta_tecnica.moto.pk,
        )
        response = self.client.get(
            reverse("notificaciones:alertas"),
            {"estado": "VENCIDO", "seguimiento": "todos"},
        )

        self.assertEqual(total, 5)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertContains(
            response,
            'href="/mantenimientos/?estado=VENCIDO&amp;seguimiento=todos&amp;page=2"',
        )

    def test_htmx_reemplaza_la_seccion_de_alertas(self):
        response = self.client.get(
            reverse("notificaciones:alertas"),
            {"page": 2},
            HTTP_HX_REQUEST="true",
        )

        self.assertNotContains(response, "<html")
        self.assertContains(response, 'id="lista-alertas"')
        self.assertContains(response, 'hx-target="#lista-alertas"')
        self.assertContains(response, 'hx-swap="outerHTML show:#lista-alertas:top"')

    def test_pagina_invalida_en_alertas_no_falla(self):
        response = self.client.get(reverse("notificaciones:alertas"), {"page": "x"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 1)
