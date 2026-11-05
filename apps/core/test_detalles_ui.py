from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.core.templatetags.formato import iniciales_usuario
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.servicios.models import Servicio


def usuario(username="mecanico", first_name="", last_name=""):
    return SimpleNamespace(
        first_name=first_name,
        last_name=last_name,
        get_username=lambda: username,
    )


class InicialesUsuarioTests(SimpleTestCase):
    def test_usa_nombre_y_apellido_en_mayuscula(self):
        self.assertEqual(iniciales_usuario(usuario(first_name="carla", last_name="pérez")), "CP")

    def test_respeta_tildes_y_enie(self):
        self.assertEqual(iniciales_usuario(usuario(first_name="Élida", last_name="ñuñez")), "ÉÑ")
        # Tilde combinada (NFD) se normaliza antes de tomar la inicial.
        self.assertEqual(iniciales_usuario(usuario(first_name="Élida")), "É")

    def test_maximo_dos_letras_aunque_haya_nombres_compuestos(self):
        self.assertEqual(
            iniciales_usuario(usuario(first_name="Ana María", last_name="de la Torre")), "AD"
        )

    def test_solo_nombre_o_solo_apellido(self):
        self.assertEqual(iniciales_usuario(usuario(first_name="Lucas")), "L")
        self.assertEqual(iniciales_usuario(usuario(last_name="Gómez")), "G")

    def test_sin_nombre_usa_la_inicial_del_username(self):
        self.assertEqual(iniciales_usuario(usuario(username="taller")), "T")
        self.assertEqual(iniciales_usuario(usuario(username="ömer", first_name="  ")), "Ö")

    def test_sin_datos_devuelve_vacio(self):
        self.assertEqual(iniciales_usuario(usuario(username="")), "")


class ShellUsuarioTests(TestCase):
    def test_topbar_y_menu_movil_muestran_iniciales_y_username_sin_nombre(self):
        cuenta = get_user_model().objects.create_user(username="taller-centro", password="x")
        self.client.force_login(cuenta)

        response = self.client.get(reverse("core:dashboard"))

        self.assertContains(response, '<span class="avatar" aria-hidden="true">T</span>', count=2)
        self.assertContains(response, "<strong>taller-centro</strong>")
        self.assertNotContains(response, "Usuario del taller")

    def test_con_nombre_completo_usa_iniciales_y_nombre(self):
        cuenta = get_user_model().objects.create_user(
            username="lmartinez", password="x", first_name="Lucía", last_name="Martínez"
        )
        self.client.force_login(cuenta)

        response = self.client.get(reverse("core:dashboard"))

        self.assertContains(response, '<span class="avatar" aria-hidden="true">LM</span>', count=2)
        self.assertContains(response, "<strong>Lucía Martínez</strong>")

    def test_hint_de_busqueda_sale_del_servidor_como_ctrl_k(self):
        cuenta = get_user_model().objects.create_user(username="taller", password="x")
        self.client.force_login(cuenta)

        response = self.client.get(reverse("core:dashboard"))

        self.assertContains(response, '<span class="search-hint" aria-hidden="true">Ctrl K</span>')


class BusquedaGlobalServiciosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="mecanico", password="x")
        cls.cliente = Cliente.objects.create(nombre="Carlos", apellido="López")
        cls.otro_cliente = Cliente.objects.create(nombre="Marta", apellido="Suárez")
        cls.moto = Moto.objects.create(
            cliente=cls.cliente, patente="AB123CD", marca="Honda", modelo="Wave"
        )
        cls.otra_moto = Moto.objects.create(
            cliente=cls.otro_cliente, patente="ZZ999ZZ", marca="Yamaha", modelo="FZ"
        )
        cls.cambio_cadena = Servicio.objects.create(
            moto=cls.moto,
            trabajos_adicionales="Cambio de kit de cadena",
            observaciones="Revisar tensor en la próxima visita",
        )
        cls.cancelado = Servicio.objects.create(
            moto=cls.otra_moto,
            estado=Servicio.Estado.CANCELADO,
            observaciones="El cliente pidió presupuesto de embrague",
        )
        tipo = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        MantenimientoRealizado.objects.create(servicio=cls.cambio_cadena, tipo_mantenimiento=tipo)

    def setUp(self):
        self.client.force_login(self.usuario)

    def buscar(self, termino):
        return self.client.get(reverse("core:search"), {"q": termino})

    def ids(self, response):
        return [servicio.pk for servicio in response.context["servicios"]]

    def test_busca_por_patente_cliente_trabajos_y_observaciones(self):
        for termino in ("AB123CD", "ab-123 cd", "López", "kit de cadena", "tensor"):
            with self.subTest(termino=termino):
                self.assertEqual(self.ids(self.buscar(termino)), [self.cambio_cadena.pk])

    def test_incluye_servicios_cancelados_con_su_estado(self):
        response = self.buscar("embrague")

        self.assertEqual(self.ids(response), [self.cancelado.pk])
        self.assertContains(response, "Cancelado")

    def test_muestra_la_seccion_con_enlace_al_detalle_y_al_listado(self):
        response = self.buscar("cadena")

        self.assertContains(response, 'id="servicios-title"')
        self.assertContains(response, reverse("servicios:detail", args=(self.cambio_cadena.pk,)))
        self.assertContains(response, f'{reverse("servicios:list")}?q=cadena')
        self.assertContains(response, "Cambio de aceite")
        self.assertContains(response, "AB123CD")

    def test_sin_coincidencias_muestra_estado_vacio(self):
        response = self.buscar("inexistente")

        self.assertContains(response, "Sin servicios")

    def test_limita_a_ocho_servicios_sin_consultas_por_fila(self):
        for numero in range(12):
            Servicio.objects.create(moto=self.moto, observaciones=f"bujía {numero}")

        with CaptureQueriesContext(connection) as consultas_doce:
            response = self.buscar("bujía")
        self.assertEqual(len(response.context["servicios"]), 8)

        Servicio.objects.filter(observaciones__startswith="bujía").exclude(
            observaciones__in=["bujía 0", "bujía 1"]
        ).delete()
        with CaptureQueriesContext(connection) as consultas_dos:
            self.buscar("bujía")

        self.assertEqual(len(consultas_doce), len(consultas_dos))

    def test_sin_termino_no_busca_servicios(self):
        response = self.client.get(reverse("core:search"))

        self.assertEqual(list(response.context["servicios"]), [])
        self.assertNotContains(response, 'id="servicios-title"')

    def test_listado_de_servicios_tambien_busca_en_observaciones(self):
        response = self.client.get(reverse("servicios:list"), {"q": "tensor"})

        self.assertEqual(
            [servicio.pk for servicio in response.context["servicios"]],
            [self.cambio_cadena.pk],
        )
