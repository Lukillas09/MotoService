from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
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


class NotificacionesAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="clave-segura",
        )
        cls.cliente = Cliente.objects.create(
            nombre="Carlos",
            apellido="Perez",
        )
        cls.moto = Moto.objects.create(
            cliente=cls.cliente,
            patente="ABC123",
            marca="Honda",
            modelo="Tornado",
        )
        cls.servicio = Servicio.objects.create(
            moto=cls.moto,
            fecha=date(2026, 1, 1),
            kilometraje=10000,
        )
        cls.tipo = TipoMantenimiento.objects.create(nombre="Prueba de admin")
        cls.mantenimiento = MantenimientoRealizado.objects.create(
            servicio=cls.servicio,
            tipo_mantenimiento=cls.tipo,
        )
        cls.seguimiento = SeguimientoMantenimiento.objects.create(
            mantenimiento_base=cls.mantenimiento,
            cliente=cls.cliente,
            estado=SeguimientoMantenimiento.Estado.CONTACTADO,
            observaciones="Seguimiento creado por el servicio de dominio.",
            actualizado_por=cls.usuario,
        )
        cls.evento = EventoSeguimientoMantenimiento.objects.create(
            seguimiento=cls.seguimiento,
            tipo_evento=EventoSeguimientoMantenimiento.Tipo.CONTACTADO,
            usuario=cls.usuario,
            nota="Contacto registrado por el servicio de dominio.",
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_seguimientos_permiten_consulta_busqueda_y_filtro(self):
        listado = self.client.get(
            reverse("admin:notificaciones_seguimientomantenimiento_changelist"),
            {
                "q": "ABC123",
                "estado__exact": SeguimientoMantenimiento.Estado.CONTACTADO,
            },
        )
        detalle = self.client.get(
            reverse(
                "admin:notificaciones_seguimientomantenimiento_change",
                args=(self.seguimiento.pk,),
            )
        )

        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, self.tipo.nombre)
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, self.seguimiento.observaciones)
        self.assertContains(detalle, self.evento.nota)
        self.assertNotContains(detalle, 'name="_save"')

    def test_eventos_permiten_consulta_busqueda_y_filtro(self):
        listado = self.client.get(
            reverse(
                "admin:notificaciones_eventoseguimientomantenimiento_changelist"
            ),
            {
                "q": "Carlos",
                "tipo_evento__exact": (
                    EventoSeguimientoMantenimiento.Tipo.CONTACTADO
                ),
            },
        )
        detalle = self.client.get(
            reverse(
                "admin:notificaciones_eventoseguimientomantenimiento_change",
                args=(self.evento.pk,),
            )
        )

        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, self.tipo.nombre)
        self.assertContains(listado, "Contactado")
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, self.evento.nota)
        self.assertNotContains(detalle, 'name="_save"')

    def test_admin_impide_alta_cambio_y_borrado_de_seguimientos(self):
        modelo_admin = admin.site._registry[SeguimientoMantenimiento]

        self.assertFalse(modelo_admin.has_add_permission(None))
        self.assertFalse(
            modelo_admin.has_change_permission(None, self.seguimiento)
        )
        self.assertFalse(
            modelo_admin.has_delete_permission(None, self.seguimiento)
        )

        respuesta = self.client.post(
            reverse(
                "admin:notificaciones_seguimientomantenimiento_change",
                args=(self.seguimiento.pk,),
            ),
            {"estado": SeguimientoMantenimiento.Estado.NO_INTERESADO},
        )

        self.assertEqual(respuesta.status_code, 403)
        self.seguimiento.refresh_from_db()
        self.assertEqual(
            self.seguimiento.estado,
            SeguimientoMantenimiento.Estado.CONTACTADO,
        )
        self.assertEqual(self.seguimiento.eventos.count(), 1)

    def test_admin_impide_alta_cambio_y_borrado_de_eventos(self):
        modelo_admin = admin.site._registry[EventoSeguimientoMantenimiento]

        self.assertFalse(modelo_admin.has_add_permission(None))
        self.assertFalse(modelo_admin.has_change_permission(None, self.evento))
        self.assertFalse(modelo_admin.has_delete_permission(None, self.evento))

        respuesta = self.client.post(
            reverse(
                "admin:notificaciones_eventoseguimientomantenimiento_change",
                args=(self.evento.pk,),
            ),
            {
                "tipo_evento": EventoSeguimientoMantenimiento.Tipo.NOTA,
                "nota": "Intento de cambio directo.",
            },
        )

        self.assertEqual(respuesta.status_code, 403)
        self.evento.refresh_from_db()
        self.assertEqual(
            self.evento.tipo_evento,
            EventoSeguimientoMantenimiento.Tipo.CONTACTADO,
        )
        self.assertEqual(
            self.evento.nota,
            "Contacto registrado por el servicio de dominio.",
        )
