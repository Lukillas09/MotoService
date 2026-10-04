from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.mantenimientos.services import EstadoMantenimiento
from apps.motos.models import Moto
from apps.servicios.models import Servicio


class MotoViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico", password="clave-segura"
        )
        cls.cliente = Cliente.objects.create(
            nombre="Carlos", apellido="González", telefono="260 4123456"
        )
        cls.cliente_archivado = Cliente.objects.create(
            nombre="Martín", apellido="Pérez", activo=False
        )
        cls.moto = Moto.objects.create(
            cliente=cls.cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado XR250",
            anio=2021,
            cilindrada_cc=250,
            kilometraje_actual=32450,
        )
        cls.moto_archivada = Moto.objects.create(
            cliente=cls.cliente,
            patente="AG456TR",
            marca="Yamaha",
            modelo="FZ",
            activo=False,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def datos_moto(self, **cambios):
        datos = {
            "cliente": self.cliente.pk,
            "patente": "AE987ZX",
            "marca": "Yamaha",
            "modelo": "MT-03",
            "anio": 2022,
            "cilindrada_cc": 321,
            "color": "Negro",
            "kilometraje_actual": 12000,
            "numero_chasis": "CHASIS-1",
            "numero_motor": "MOTOR-1",
            "observaciones": "Sin novedades",
        }
        datos.update(cambios)
        return datos

    def test_todas_las_vistas_requieren_login(self):
        cliente_anonimo = TestClient()
        solicitudes = (
            ("get", reverse("motos:list")),
            ("get", reverse("motos:create")),
            ("get", reverse("motos:detail", args=(self.moto.pk,))),
            ("get", reverse("motos:update", args=(self.moto.pk,))),
            ("post", reverse("motos:archive", args=(self.moto.pk,))),
            ("post", reverse("motos:restore", args=(self.moto_archivada.pk,))),
        )

        for metodo, url in solicitudes:
            with self.subTest(url=url):
                response = getattr(cliente_anonimo, metodo)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_listado_muestra_activas_y_propietario(self):
        response = self.client.get(reverse("motos:list"))

        self.assertContains(response, "AF123XY")
        self.assertContains(response, "Carlos González")
        self.assertContains(response, "32.450 km")
        self.assertNotContains(response, "AG456TR")

    def test_listado_de_archivadas(self):
        response = self.client.get(reverse("motos:list"), {"estado": "archivadas"})

        self.assertContains(response, "AG456TR")
        self.assertNotContains(response, "AF123XY")
        self.assertContains(response, "Restaurar")

    def test_busqueda_por_patente_modelo_y_cliente(self):
        consultas = ("af-123 xy", "Tornado", "González", "2604")

        for termino in consultas:
            with self.subTest(termino=termino):
                response = self.client.get(reverse("motos:list"), {"q": termino})
                self.assertContains(response, "AF123XY")

    def test_busqueda_htmx_devuelve_solo_el_parcial(self):
        response = self.client.get(
            reverse("motos:list"),
            {"q": "Tornado"},
            HTTP_HX_REQUEST="true",
        )

        self.assertTemplateUsed(response, "motos/partials/lista.html")
        self.assertNotContains(response, "<!doctype html>")

    def test_formulario_preselecciona_cliente_desde_querystring(self):
        response = self.client.get(
            reverse("motos:create"), {"cliente": self.cliente.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["cliente"], self.cliente)

    def test_cliente_inicial_invalido_devuelve_404(self):
        response = self.client.get(reverse("motos:create"), {"cliente": "abc"})

        self.assertEqual(response.status_code, 404)

    def test_crear_moto_normaliza_patente_y_redirige_al_detalle(self):
        response = self.client.post(
            reverse("motos:create"),
            self.datos_moto(patente="ae-987 zx"),
            follow=True,
        )

        moto = Moto.objects.get(patente="AE987ZX")
        self.assertEqual(moto.kilometraje_actual, 12000)
        self.assertRedirects(response, reverse("motos:detail", args=(moto.pk,)))
        self.assertContains(response, "Moto creada correctamente.")

    def test_crear_moto_rechaza_patente_duplicada(self):
        response = self.client.post(
            reverse("motos:create"), self.datos_moto(patente="af-123-xy")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("patente", response.context["form"].errors)

    def test_no_permite_asignar_nueva_moto_a_cliente_archivado(self):
        response = self.client.post(
            reverse("motos:create"),
            self.datos_moto(cliente=self.cliente_archivado.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("cliente", response.context["form"].errors)

    def test_detalle_muestra_datos_e_historial_vacio(self):
        response = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))

        self.assertContains(response, "Honda Tornado XR250")
        self.assertContains(response, "250 cc")
        self.assertContains(response, "32.450 km")
        self.assertContains(response, "Todavía no hay servicios registrados.")

    def test_detalle_muestra_estados_de_todas_las_reglas_activas(self):
        aceite = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        aceite.genera_recordatorio = True
        aceite.intervalo_km = 3000
        aceite.aviso_km = 1000
        aceite.save()
        filtro = TipoMantenimiento.objects.get(nombre="Filtro de aire")
        filtro.genera_recordatorio = True
        filtro.intervalo_meses = 12
        filtro.save()
        servicio = Servicio.objects.create(
            moto=self.moto,
            fecha=timezone.localdate(),
            kilometraje=30000,
        )
        MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=aceite,
        )

        response = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))

        estados = {
            estado.tipo_mantenimiento.nombre: estado.estado
            for estado in response.context["estados_mantenimiento"]
        }
        self.assertEqual(estados["Cambio de aceite"], EstadoMantenimiento.PROXIMO)
        self.assertEqual(estados["Filtro de aire"], EstadoMantenimiento.SIN_REGISTRO)
        self.assertContains(response, "Estado de mantenimientos")
        self.assertContains(response, "33.000 km")
        self.assertContains(response, "Sin registro")
        self.assertContains(response, "https://wa.me/")

    def test_detalle_omite_recordatorios_desactivados(self):
        aceite = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        aceite.intervalo_meses = 12
        aceite.genera_recordatorio = False
        aceite.save()

        response = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))

        self.assertEqual(response.context["estados_mantenimiento"], ())
        self.assertContains(response, "No hay reglas de mantenimiento activas.")

    def test_editar_moto_vuelve_a_normalizar_patente(self):
        response = self.client.post(
            reverse("motos:update", args=(self.moto.pk,)),
            self.datos_moto(
                patente=" zz-999 aa ",
                kilometraje_actual=self.moto.kilometraje_actual,
            ),
            follow=True,
        )

        self.moto.refresh_from_db()
        self.assertEqual(self.moto.patente, "ZZ999AA")
        self.assertContains(response, "Moto actualizada correctamente.")

    def test_editar_moto_rechaza_kilometraje_menor_y_conserva_el_real(self):
        moto = Moto.objects.create(
            cliente=self.cliente,
            marca="Honda",
            modelo="Wave",
            kilometraje_actual=12000,
        )

        response = self.client.post(
            reverse("motos:update", args=(moto.pk,)),
            self.datos_moto(patente="AB123CD", kilometraje_actual=9000),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("kilometraje_actual", response.context["form"].errors)
        self.assertContains(
            response,
            "El kilometraje no puede ser menor al último registrado (12.000 km).",
        )
        moto.refresh_from_db()
        self.assertEqual(moto.kilometraje_actual, 12000)

    def test_editar_moto_permite_kilometraje_igual(self):
        response = self.client.post(
            reverse("motos:update", args=(self.moto.pk,)),
            self.datos_moto(kilometraje_actual=32450),
            follow=True,
        )

        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 32450)
        self.assertContains(response, "Moto actualizada correctamente.")

    def test_editar_moto_permite_aumentar_kilometraje(self):
        response = self.client.post(
            reverse("motos:update", args=(self.moto.pk,)),
            self.datos_moto(kilometraje_actual=33000),
            follow=True,
        )

        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 33000)
        self.assertContains(response, "Moto actualizada correctamente.")

    def test_edicion_conserva_cliente_archivado_actual_como_opcion(self):
        moto = Moto.objects.create(
            cliente=self.cliente_archivado, marca="Honda", modelo="Biz"
        )

        response = self.client.get(reverse("motos:update", args=(moto.pk,)))

        self.assertIn(self.cliente_archivado, response.context["form"].fields["cliente"].queryset)

    def test_archivar_y_restaurar_son_post(self):
        archive_url = reverse("motos:archive", args=(self.moto.pk,))
        restore_url = reverse("motos:restore", args=(self.moto.pk,))

        self.assertEqual(self.client.get(archive_url).status_code, 405)
        archive_response = self.client.post(archive_url, follow=True)
        self.moto.refresh_from_db()
        self.assertFalse(self.moto.activo)
        self.assertContains(archive_response, "Moto archivada.")

        self.assertEqual(self.client.get(restore_url).status_code, 405)
        restore_response = self.client.post(restore_url, follow=True)
        self.moto.refresh_from_db()
        self.assertTrue(self.moto.activo)
        self.assertContains(restore_response, "Moto restaurada.")

    def test_id_inexistente_devuelve_404(self):
        response = self.client.get(reverse("motos:detail", args=(999999,)))

        self.assertEqual(response.status_code, 404)
