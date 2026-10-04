from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.notificaciones.models import (
    EventoSeguimientoMantenimiento,
    SeguimientoMantenimiento,
)

from apps.servicios.models import Servicio


class ServicioViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico",
            password="clave-segura",
        )
        cls.cliente = Cliente.objects.create(
            nombre="Carlos",
            apellido="González",
            telefono="260 4123456",
        )
        cls.otro_cliente = Cliente.objects.create(nombre="Ana", apellido="Pérez")
        cls.moto = Moto.objects.create(
            cliente=cls.cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
            kilometraje_actual=10000,
        )
        cls.moto_archivada = Moto.objects.create(
            cliente=cls.cliente,
            marca="Yamaha",
            modelo="FZ",
            activo=False,
        )
        cls.aceite = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        cls.filtro = TipoMantenimiento.objects.get(nombre="Filtro de aceite")

    def setUp(self):
        self.client.force_login(self.usuario)

    def datos_servicio(self, **cambios):
        datos = {
            "moto": self.moto.pk,
            "fecha": date.today().isoformat(),
            "kilometraje": 12000,
            "estado": Servicio.Estado.FINALIZADO,
            "mantenimientos": [self.aceite.pk, self.filtro.pk],
            "trabajos_adicionales": "Ajuste de embrague",
            "observaciones": "Controlar en la próxima visita",
            "precio_total": "75000.00",
        }
        datos.update(cambios)
        return datos

    def crear_servicio(self, **cambios):
        datos = {
            "moto": self.moto,
            "fecha": date.today(),
            "kilometraje": 11000,
            "creado_por": self.usuario,
        }
        datos.update(cambios)
        return Servicio.objects.create(**datos)

    def test_todas_las_vistas_requieren_login(self):
        servicio = self.crear_servicio()
        anonimo = TestClient()
        solicitudes = (
            ("get", reverse("servicios:list"), {}),
            ("get", reverse("servicios:create"), {}),
            ("get", reverse("servicios:detail", args=(servicio.pk,)), {}),
            ("get", reverse("servicios:update", args=(servicio.pk,)), {}),
            ("post", reverse("servicios:cancel", args=(servicio.pk,)), {}),
            ("get", reverse("servicios:moto_context"), {"moto": self.moto.pk}),
        )

        for metodo, url, datos in solicitudes:
            with self.subTest(url=url):
                response = getattr(anonimo, metodo)(url, datos)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_formulario_preselecciona_moto_y_muestra_contexto(self):
        response = self.client.get(
            reverse("servicios:create"),
            {"moto": self.moto.pk},
        )

        self.assertEqual(response.context["form"].initial["moto"], self.moto)
        self.assertContains(response, "Carlos González")
        self.assertContains(response, "10.000 km")

    def test_preseleccion_invalida_o_no_disponible_devuelve_404(self):
        for moto in ("abc", self.moto_archivada.pk, 999999):
            with self.subTest(moto=moto):
                response = self.client.get(reverse("servicios:create"), {"moto": moto})
                self.assertEqual(response.status_code, 404)

    def test_crea_servicio_con_cliente_usuario_mantenimientos_y_kilometraje(self):
        response = self.client.post(
            reverse("servicios:create"),
            self.datos_servicio(
                cliente=self.otro_cliente.pk,
                creado_por=get_user_model().objects.create_user(username="intruso").pk,
            ),
            follow=True,
        )

        servicio = Servicio.objects.get()
        self.assertRedirects(response, reverse("servicios:detail", args=(servicio.pk,)))
        self.assertEqual(servicio.cliente, self.cliente)
        self.assertEqual(servicio.creado_por, self.usuario)
        self.assertEqual(servicio.mantenimientos_realizados.count(), 2)
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 12000)
        self.assertContains(response, "$ 75.000,00")
        ficha_moto = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))
        self.assertContains(ficha_moto, "12.000 km")

    def test_moto_archivada_no_acepta_servicio_por_post(self):
        response = self.client.post(
            reverse("servicios:create"),
            self.datos_servicio(moto=self.moto_archivada.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("moto", response.context["form"].errors)
        self.assertFalse(Servicio.objects.filter(moto=self.moto_archivada).exists())

    def test_kilometraje_menor_requiere_confirmacion_y_no_reduce_la_moto(self):
        invalido = self.client.post(
            reverse("servicios:create"),
            self.datos_servicio(kilometraje=9000),
        )
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, "Confirmá el kilometraje menor")
        self.assertFalse(Servicio.objects.exists())

        confirmado = self.client.post(
            reverse("servicios:create"),
            self.datos_servicio(
                kilometraje=9000,
                confirmar_kilometraje_menor="on",
            ),
        )
        self.assertEqual(confirmado.status_code, 302)
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 10000)

    def test_listado_busca_filtra_y_responde_parcial_htmx(self):
        visible = self.crear_servicio(trabajos_adicionales="Cambio de retenes")
        self.crear_servicio(
            moto=Moto.objects.create(
                cliente=self.otro_cliente,
                patente="ZZ999ZZ",
                marca="Yamaha",
                modelo="FZ",
            ),
            estado=Servicio.Estado.CANCELADO,
            fecha=date.today() - timedelta(days=30),
        )

        response = self.client.get(reverse("servicios:list"), {"q": "retenes"})
        self.assertContains(response, "AF123XY")
        self.assertNotContains(response, "ZZ999ZZ")

        htmx = self.client.get(
            reverse("servicios:list"),
            {"estado": Servicio.Estado.CANCELADO},
            HTTP_HX_REQUEST="true",
        )
        self.assertTemplateUsed(htmx, "servicios/partials/lista.html")
        self.assertContains(htmx, "ZZ999ZZ")
        self.assertNotContains(htmx, "<!doctype html>")
        self.assertTrue(Servicio.objects.filter(pk=visible.pk).exists())

    def test_edicion_conserva_moto_cliente_historico_y_creador(self):
        servicio = self.crear_servicio()
        cliente_historico = servicio.cliente
        self.moto.cliente = self.otro_cliente
        self.moto.save()
        otra_moto = Moto.objects.create(
            cliente=self.otro_cliente,
            marca="Suzuki",
            modelo="GN",
        )

        response = self.client.post(
            reverse("servicios:update", args=(servicio.pk,)),
            {
                "moto": otra_moto.pk,
                "fecha": servicio.fecha.isoformat(),
                "kilometraje": 11500,
                "estado": Servicio.Estado.ABIERTO,
                "mantenimientos": [self.aceite.pk],
                "trabajos_adicionales": "Trabajo editado",
                "observaciones": "",
                "precio_total": "1000",
            },
            follow=True,
        )

        servicio.refresh_from_db()
        self.assertEqual(servicio.moto, self.moto)
        self.assertEqual(servicio.cliente, cliente_historico)
        self.assertEqual(servicio.creado_por, self.usuario)
        self.assertEqual(servicio.estado, Servicio.Estado.ABIERTO)
        self.assertContains(response, "Servicio actualizado correctamente.")

    def test_edicion_no_quita_mantenimiento_con_seguimiento(self):
        servicio = self.crear_servicio(trabajos_adicionales="Trabajo original")
        mantenimiento = MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=self.aceite,
        )
        MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=self.filtro,
        )
        seguimiento = SeguimientoMantenimiento.objects.create(
            mantenimiento_base=mantenimiento,
            cliente=servicio.cliente,
        )
        evento = EventoSeguimientoMantenimiento.objects.create(
            seguimiento=seguimiento,
            tipo_evento=EventoSeguimientoMantenimiento.Tipo.NOTA,
            nota="Conservar este historial",
        )

        response = self.client.post(
            reverse("servicios:update", args=(servicio.pk,)),
            self.datos_servicio(
                mantenimientos=[self.filtro.pk],
                trabajos_adicionales="Trabajo modificado",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cambio de aceite")
        self.assertContains(response, "seguimiento y su historial deben conservarse")
        self.assertIn("mantenimientos", response.context["form"].errors)
        servicio.refresh_from_db()
        self.assertEqual(servicio.kilometraje, 11000)
        self.assertEqual(servicio.trabajos_adicionales, "Trabajo original")
        self.assertSetEqual(
            set(
                servicio.mantenimientos_realizados.values_list(
                    "tipo_mantenimiento_id", flat=True
                )
            ),
            {self.aceite.pk, self.filtro.pk},
        )
        self.assertTrue(
            SeguimientoMantenimiento.objects.filter(pk=seguimiento.pk).exists()
        )
        self.assertTrue(
            EventoSeguimientoMantenimiento.objects.filter(pk=evento.pk).exists()
        )

    def test_cancelar_es_post_conserva_registro_y_no_reduce_kilometraje(self):
        servicio = self.crear_servicio(kilometraje=13000)
        url = reverse("servicios:cancel", args=(servicio.pk,))

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, follow=True)
        servicio.refresh_from_db()
        self.assertEqual(servicio.estado, Servicio.Estado.CANCELADO)
        self.assertTrue(Servicio.objects.filter(pk=servicio.pk).exists())
        self.assertContains(response, "se conserva como parte del historial")
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 13000)

    def test_detalle_de_moto_muestra_historial_incluso_cancelado(self):
        servicio = self.crear_servicio(estado=Servicio.Estado.CANCELADO)
        MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=self.aceite,
        )

        response = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))

        self.assertContains(response, "Cambio de aceite")
        self.assertContains(response, "Cancelado")
        self.assertContains(response, reverse("servicios:detail", args=(servicio.pk,)))

    def test_contexto_moto_htmx_muestra_propietario_y_kilometraje(self):
        response = self.client.get(
            reverse("servicios:moto_context"),
            {"moto": self.moto.pk},
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, "Carlos González")
        self.assertContains(response, "10.000 km")
        self.assertNotContains(response, "<!doctype html>")

    def test_filtro_de_fechas_valida_el_rango(self):
        response = self.client.get(
            reverse("servicios:list"),
            {"desde": "2026-10-10", "hasta": "2026-10-01"},
        )

        self.assertContains(response, "La fecha desde no puede ser posterior")

    def test_admin_de_servicio_carga_con_inline_de_mantenimientos(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save()
        servicio = self.crear_servicio()

        alta = self.client.get(reverse("admin:servicios_servicio_add"))
        edicion = self.client.get(
            reverse("admin:servicios_servicio_change", args=(servicio.pk,))
        )

        self.assertEqual(alta.status_code, 200)
        self.assertEqual(edicion.status_code, 200)
        self.assertContains(edicion, "Mantenimientos realizados")
