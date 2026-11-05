from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.notificaciones.models import (
    EventoSeguimientoMantenimiento,
    SeguimientoMantenimiento,
)
from apps.servicios.models import Servicio


class SeguimientoViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="mecanico",
            password="clave-segura",
        )
        cls.cliente = Cliente.objects.create(
            nombre="Carlos",
            apellido="González",
            telefono="261 555-1000",
        )
        cls.moto = Moto.objects.create(
            cliente=cls.cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
            kilometraje_actual=20000,
        )
        cls.tipo = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        cls.tipo.activo = True
        cls.tipo.genera_recordatorio = True
        cls.tipo.intervalo_meses = None
        cls.tipo.intervalo_km = 5000
        cls.tipo.aviso_km = 500
        cls.tipo.save()
        servicio = Servicio.objects.create(
            moto=cls.moto,
            fecha=timezone.localdate() - timedelta(days=365),
            kilometraje=10000,
        )
        cls.base = MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=cls.tipo,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def url(self, nombre):
        return reverse(
            f"notificaciones:{nombre}",
            args=(self.moto.pk, self.tipo.pk),
        )

    def datos(self, **cambios):
        datos = {"mantenimiento_base": self.base.pk}
        datos.update(cambios)
        return datos

    def test_vistas_requieren_login(self):
        anonimo = TestClient()
        urls = (
            reverse("notificaciones:alertas"),
            self.url("historial"),
            self.url("contactar"),
            self.url("posponer"),
            self.url("turno"),
            self.url("no_interesado"),
            self.url("reabrir"),
            self.url("nota"),
        )

        for url in urls:
            with self.subTest(url=url):
                response = anonimo.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_mutaciones_solo_aceptan_post(self):
        for nombre in (
            "contactar",
            "posponer",
            "turno",
            "no_interesado",
            "reabrir",
            "nota",
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(self.url(nombre)).status_code, 405)
        self.assertFalse(SeguimientoMantenimiento.objects.exists())

    def test_post_sin_csrf_es_rechazado(self):
        cliente_csrf = TestClient(enforce_csrf_checks=True)
        cliente_csrf.force_login(self.usuario)

        response = cliente_csrf.post(self.url("contactar"), self.datos())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(SeguimientoMantenimiento.objects.exists())

    def test_lecturas_muestran_pendiente_sin_crear_filas(self):
        urls = (
            reverse("notificaciones:alertas"),
            reverse("core:dashboard"),
            reverse("motos:detail", args=(self.moto.pk,)),
            self.url("historial"),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

        self.assertFalse(SeguimientoMantenimiento.objects.exists())
        response = self.client.get(reverse("notificaciones:alertas"))
        self.assertContains(response, "Pendiente")

    def test_whatsapp_es_link_seguro_y_no_muta(self):
        response = self.client.get(reverse("notificaciones:alertas"))

        self.assertContains(response, "https://wa.me/")
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertFalse(SeguimientoMantenimiento.objects.exists())
        self.assertFalse(EventoSeguimientoMantenimiento.objects.exists())

    def test_marcar_contactado_crea_estado_evento_y_mensaje(self):
        response = self.client.post(
            self.url("contactar"),
            self.datos(nota="Confirmó recepción."),
            follow=True,
        )

        self.assertRedirects(response, reverse("notificaciones:alertas"))
        self.assertContains(response, "Cliente marcado como contactado.")
        self.assertContains(response, "Contactado")
        seguimiento = SeguimientoMantenimiento.objects.get()
        self.assertEqual(
            seguimiento.estado,
            SeguimientoMantenimiento.Estado.CONTACTADO,
        )
        self.assertEqual(seguimiento.eventos.count(), 1)

    def test_pospuesto_no_aparece_por_defecto_pero_si_en_su_filtro(self):
        response = self.client.post(
            self.url("posponer"),
            self.datos(plazo="7", nota="Llamar la semana próxima."),
            follow=True,
        )

        self.assertContains(response, "No hay clientes que requieran seguimiento ahora")
        filtrado = self.client.get(
            reverse("notificaciones:alertas"),
            {"seguimiento": "pospuestos"},
        )
        self.assertContains(filtrado, "Pospuesto")
        self.assertContains(filtrado, "AF123XY")

    def test_turno_valida_fecha_futura(self):
        response = self.client.post(
            self.url("turno"),
            self.datos(turno_para="2000-01-01T10:00"),
            follow=True,
        )

        self.assertContains(response, "El turno debe ser posterior")
        self.assertFalse(SeguimientoMantenimiento.objects.exists())

    def test_no_interesado_se_filtra_y_reabrir_lo_devuelve_a_pendiente(self):
        self.client.post(
            self.url("no_interesado"),
            self.datos(nota="No lo hará por ahora."),
        )
        response = self.client.get(
            reverse("notificaciones:alertas"),
            {"seguimiento": "no_interesados"},
        )
        self.assertContains(response, "No interesado")

        response = self.client.post(
            self.url("reabrir"),
            self.datos(nota="Pidió que lo llamemos."),
            follow=True,
        )

        self.assertContains(response, "Seguimiento reabierto.")
        self.assertContains(response, "Pendiente")
        self.assertEqual(
            SeguimientoMantenimiento.objects.get().eventos.count(),
            2,
        )

    def test_historial_muestra_eventos_y_usuario_en_orden(self):
        self.client.post(self.url("contactar"), self.datos(nota="Primer contacto"))
        self.client.post(
            self.url("posponer"),
            self.datos(plazo="7", nota="Esperar"),
        )
        self.client.post(self.url("reabrir"), self.datos(nota="Retomar"))

        response = self.client.get(self.url("historial"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Primer contacto")
        self.assertContains(response, "Esperar")
        self.assertContains(response, "Retomar")
        self.assertContains(response, f"por {self.usuario.username}", count=3)
        eventos = list(response.context["eventos"])
        self.assertEqual(
            [evento.tipo_evento for evento in eventos],
            [
                EventoSeguimientoMantenimiento.Tipo.CONTACTADO,
                EventoSeguimientoMantenimiento.Tipo.POSPUESTO,
                EventoSeguimientoMantenimiento.Tipo.REABIERTO,
            ],
        )

    def test_htmx_devuelve_solo_lista_y_filtros_siguen_funcionando(self):
        response = self.client.get(
            reverse("notificaciones:alertas"),
            {"q": "af-123-xy", "estado": "VENCIDO"},
            HTTP_HX_REQUEST="true",
        )

        self.assertTemplateUsed(
            response,
            "mantenimientos/partials/lista_alertas.html",
        )
        self.assertNotContains(response, "<!doctype html>")
        self.assertContains(response, "AF123XY")

    def test_pagina_obsoleta_no_registra_accion(self):
        nuevo_servicio = Servicio.objects.create(
            moto=self.moto,
            fecha=timezone.localdate(),
            kilometraje=15000,
        )
        MantenimientoRealizado.objects.create(
            servicio=nuevo_servicio,
            tipo_mantenimiento=self.tipo,
        )

        response = self.client.post(
            self.url("contactar"),
            self.datos(),
            follow=True,
        )

        self.assertContains(response, "La alerta cambió")
        self.assertFalse(SeguimientoMantenimiento.objects.exists())

    def test_formulario_invalido_no_crea_seguimiento(self):
        response = self.client.post(
            self.url("posponer"),
            self.datos(plazo="personalizada", fecha_personalizada=""),
            follow=True,
        )

        self.assertContains(response, "Elegí la fecha")
        self.assertFalse(SeguimientoMantenimiento.objects.exists())

    def test_dashboard_conserva_conteo_tecnico_y_oculta_pospuesto_de_atencion(self):
        self.client.post(self.url("posponer"), self.datos(plazo="7"))

        response = self.client.get(reverse("core:dashboard"))

        cards = {card["label"]: card["value"] for card in response.context["cards"]}
        self.assertEqual(cards["Mantenimientos vencidos"], 1)
        self.assertEqual(response.context["alertas_prioritarias"], ())
        self.assertContains(response, "0 ahora")
        self.assertContains(response, "No hay clientes que requieran seguimiento ahora")

    def test_moto_muestra_seguimiento_solo_en_estado_operativo(self):
        response = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))
        self.assertContains(response, "Pendiente")
        self.assertContains(response, "Ver seguimiento")

        self.tipo.intervalo_km = 50000
        self.tipo.save()
        response = self.client.get(reverse("motos:detail", args=(self.moto.pk,)))

        self.assertContains(response, "Al día")
        self.assertNotContains(response, "Ver seguimiento")

    def test_accion_deriva_al_propietario_actual(self):
        martin = Cliente.objects.create(nombre="Martín", telefono="261 444-2222")
        self.moto.cliente = martin
        self.moto.save()

        self.client.post(self.url("contactar"), self.datos())

        seguimiento = SeguimientoMantenimiento.objects.get()
        self.assertEqual(seguimiento.cliente, martin)
        self.assertNotEqual(seguimiento.cliente, self.base.servicio.cliente)
