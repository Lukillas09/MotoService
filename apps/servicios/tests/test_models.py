from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.notificaciones.models import (
    EventoSeguimientoMantenimiento,
    SeguimientoMantenimiento,
)

from apps.servicios.models import Servicio
from apps.servicios.services import guardar_servicio_y_mantenimientos


class ServicioModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="mecanico")
        cls.otro_usuario = get_user_model().objects.create_user(username="encargado")
        cls.cliente = Cliente.objects.create(nombre="Carlos", apellido="González")
        cls.otro_cliente = Cliente.objects.create(nombre="Ana", apellido="Pérez")
        cls.moto = Moto.objects.create(
            cliente=cls.cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
            kilometraje_actual=10000,
        )

    def test_asigna_cliente_desde_la_moto_y_lo_conserva_como_historico(self):
        servicio = Servicio.objects.create(
            moto=self.moto,
            cliente=self.otro_cliente,
            creado_por=self.usuario,
        )
        self.assertEqual(servicio.cliente, self.cliente)

        self.moto.cliente = self.otro_cliente
        self.moto.save()
        servicio.refresh_from_db()

        self.assertEqual(servicio.cliente, self.cliente)
        self.assertEqual(servicio.moto.cliente, self.otro_cliente)

    def test_creacion_aplica_fecha_estado_precio_creador_y_str(self):
        servicio = Servicio.objects.create(
            moto=self.moto,
            precio_total=Decimal("75000.50"),
            creado_por=self.usuario,
        )

        self.assertEqual(servicio.fecha, timezone.localdate())
        self.assertEqual(servicio.estado, Servicio.Estado.FINALIZADO)
        self.assertEqual(servicio.precio_total, Decimal("75000.50"))
        self.assertEqual(servicio.creado_por, self.usuario)
        self.assertEqual(servicio.moto, self.moto)
        self.assertEqual(
            str(servicio),
            f"{timezone.localdate():%d/%m/%Y} — Honda Tornado — AF123XY",
        )

    def test_no_crea_servicio_para_moto_o_cliente_archivado(self):
        self.moto.activo = False
        self.moto.save()
        with self.assertRaises(ValidationError):
            Servicio.objects.create(moto=self.moto)

        self.moto.activo = True
        self.moto.save()
        self.cliente.activo = False
        self.cliente.save()
        with self.assertRaises(ValidationError):
            Servicio.objects.create(moto=self.moto)

    def test_moto_cliente_y_creador_son_inmutables(self):
        servicio = Servicio.objects.create(
            moto=self.moto,
            creado_por=self.usuario,
        )
        otra_moto = Moto.objects.create(
            cliente=self.otro_cliente,
            marca="Yamaha",
            modelo="FZ",
        )

        cambios = (
            ("moto", otra_moto),
            ("cliente", self.otro_cliente),
            ("creado_por", self.otro_usuario),
        )
        for campo, valor in cambios:
            with self.subTest(campo=campo):
                servicio.refresh_from_db()
                setattr(servicio, campo, valor)
                with self.assertRaises(ValidationError):
                    servicio.save()

    def test_solo_un_kilometraje_mayor_actualiza_la_moto(self):
        Servicio.objects.create(moto=self.moto, kilometraje=12500)
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 12500)

        Servicio.objects.create(
            moto=self.moto,
            kilometraje=9000,
            fecha=date(2024, 1, 10),
        )
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 12500)

    def test_servicio_cancelado_no_actualiza_kilometraje(self):
        Servicio.objects.create(
            moto=self.moto,
            kilometraje=15000,
            estado=Servicio.Estado.CANCELADO,
        )

        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 10000)

    def test_precio_no_admite_valores_negativos(self):
        with self.assertRaises(ValidationError):
            Servicio.objects.create(
                moto=self.moto,
                precio_total=Decimal("-0.01"),
            )

    def test_moto_y_cliente_estan_protegidos_y_usuario_puede_eliminarse(self):
        servicio = Servicio.objects.create(
            moto=self.moto,
            creado_por=self.usuario,
        )

        with self.assertRaises(ProtectedError), transaction.atomic():
            self.moto.delete()

        self.moto.cliente = self.otro_cliente
        self.moto.save()
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.cliente.delete()

        self.usuario.delete()
        servicio.refresh_from_db()
        self.assertIsNone(servicio.creado_por)

    def test_busqueda_combina_patente_cliente_telefono_y_trabajo(self):
        self.cliente.telefono = "+54 9 260 4123456"
        self.cliente.save()
        servicio = Servicio.objects.create(
            moto=self.moto,
            trabajos_adicionales="Regulación de válvulas",
        )
        MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=TipoMantenimiento.objects.get(
                nombre="Cambio de aceite"
            ),
        )

        for termino in (
            "af-123-xy",
            "Carlos",
            "2604",
            "válvulas",
            "Honda Tornado",
            "aceite",
        ):
            with self.subTest(termino=termino):
                self.assertQuerySetEqual(Servicio.objects.buscar(termino), [servicio])


class GuardarServicioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="mecanico")
        cliente = Cliente.objects.create(nombre="Carlos")
        cls.moto = Moto.objects.create(
            cliente=cliente,
            marca="Honda",
            modelo="Wave",
            kilometraje_actual=1000,
        )
        cls.aceite = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        cls.filtro = TipoMantenimiento.objects.get(nombre="Filtro de aceite")
        cls.aire = TipoMantenimiento.objects.get(nombre="Filtro de aire")

    def test_guarda_y_sincroniza_mantenimientos(self):
        servicio = guardar_servicio_y_mantenimientos(
            Servicio(moto=self.moto, kilometraje=1500),
            [self.aceite, self.filtro],
            creado_por=self.usuario,
        )
        self.assertEqual(servicio.creado_por, self.usuario)
        self.assertSetEqual(
            set(
                servicio.mantenimientos_realizados.values_list(
                    "tipo_mantenimiento__nombre", flat=True
                )
            ),
            {"Cambio de aceite", "Filtro de aceite"},
        )

        guardar_servicio_y_mantenimientos(servicio, [self.aceite, self.aire])
        self.assertSetEqual(
            set(
                servicio.mantenimientos_realizados.values_list(
                    "tipo_mantenimiento__nombre", flat=True
                )
            ),
            {"Cambio de aceite", "Filtro de aire"},
        )

    def test_operacion_completa_revierte_si_falla_un_mantenimiento(self):
        servicio = Servicio(moto=self.moto, kilometraje=2000)

        with patch.object(
            MantenimientoRealizado.objects,
            "bulk_create",
            side_effect=RuntimeError("fallo simulado"),
        ), self.assertRaises(RuntimeError):
            guardar_servicio_y_mantenimientos(servicio, [self.aceite])

        self.assertFalse(Servicio.objects.filter(kilometraje=2000).exists())
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 1000)

    def test_no_quita_mantenimiento_con_seguimiento_y_revierte_la_edicion(self):
        servicio = guardar_servicio_y_mantenimientos(
            Servicio(
                moto=self.moto,
                kilometraje=1500,
                trabajos_adicionales="Trabajo original",
            ),
            [self.aceite, self.filtro],
        )
        mantenimiento = servicio.mantenimientos_realizados.get(
            tipo_mantenimiento=self.aceite
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

        servicio.kilometraje = 2000
        servicio.trabajos_adicionales = "Trabajo modificado"
        with self.assertRaises(ValidationError) as contexto:
            guardar_servicio_y_mantenimientos(servicio, [self.filtro])

        self.assertIn("mantenimientos", contexto.exception.message_dict)
        self.assertIn(
            "Cambio de aceite",
            contexto.exception.message_dict["mantenimientos"][0],
        )
        servicio.refresh_from_db()
        self.moto.refresh_from_db()
        self.assertEqual(servicio.kilometraje, 1500)
        self.assertEqual(servicio.trabajos_adicionales, "Trabajo original")
        self.assertEqual(self.moto.kilometraje_actual, 1500)
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
