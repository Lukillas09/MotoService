from datetime import date

from django.test import TestCase

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto

from apps.servicios.forms import ServicioForm
from apps.servicios.models import Servicio


class ServicioFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nombre="Carlos")
        cls.cliente_archivado = Cliente.objects.create(nombre="Ana")
        cls.moto = Moto.objects.create(
            cliente=cls.cliente,
            marca="Honda",
            modelo="Tornado",
            kilometraje_actual=20000,
        )
        cls.moto_archivada = Moto.objects.create(
            cliente=cls.cliente,
            marca="Yamaha",
            modelo="FZ",
            activo=False,
        )
        cls.moto_cliente_archivado = Moto.objects.create(
            cliente=cls.cliente_archivado,
            marca="Honda",
            modelo="Biz",
        )
        cls.cliente_archivado.activo = False
        cls.cliente_archivado.save(update_fields=("activo", "actualizado_en"))
        cls.aceite = TipoMantenimiento.objects.get(nombre="Cambio de aceite")

    def datos(self, **cambios):
        datos = {
            "moto": self.moto.pk,
            "fecha": date.today().isoformat(),
            "kilometraje": 20500,
            "estado": Servicio.Estado.FINALIZADO,
            "mantenimientos": [self.aceite.pk],
            "trabajos_adicionales": "",
            "observaciones": "",
            "precio_total": "25000.00",
        }
        datos.update(cambios)
        return datos

    def test_solo_ofrece_motos_activas_con_cliente_activo(self):
        form = ServicioForm()

        self.assertIn(self.moto, form.fields["moto"].queryset)
        self.assertNotIn(self.moto_archivada, form.fields["moto"].queryset)
        self.assertNotIn(self.moto_cliente_archivado, form.fields["moto"].queryset)
        self.assertIn("Carlos", form.fields["moto"].label_from_instance(self.moto))

    def test_kilometraje_menor_requiere_confirmacion_explicita(self):
        form = ServicioForm(data=self.datos(kilometraje=19000))
        self.assertFalse(form.is_valid())
        self.assertIn("confirmar_kilometraje_menor", form.errors)

        confirmado = ServicioForm(
            data=self.datos(
                kilometraje=19000,
                confirmar_kilometraje_menor="on",
            )
        )
        self.assertTrue(confirmado.is_valid(), confirmado.errors)

    def test_edicion_no_expone_moto_y_no_reconfirma_valor_historico_sin_cambios(self):
        servicio = Servicio.objects.create(moto=self.moto, kilometraje=18000)
        form = ServicioForm(
            data={
                "fecha": servicio.fecha.isoformat(),
                "kilometraje": 18000,
                "estado": Servicio.Estado.FINALIZADO,
                "mantenimientos": [],
                "trabajos_adicionales": "Control",
                "observaciones": "",
                "precio_total": "",
            },
            instance=servicio,
        )

        self.assertNotIn("moto", form.fields)
        self.assertTrue(form.is_valid(), form.errors)

    def test_tipo_inactivo_solo_se_ofrece_si_ya_es_parte_del_servicio(self):
        inactivo = TipoMantenimiento.objects.create(nombre="Trabajo discontinuado")
        inactivo.activo = False
        inactivo.save()
        self.assertNotIn(inactivo, ServicioForm().fields["mantenimientos"].queryset)

        servicio = Servicio.objects.create(moto=self.moto)
        MantenimientoRealizado.objects.create(
            servicio=servicio,
            tipo_mantenimiento=inactivo,
        )
        form = ServicioForm(instance=servicio)

        self.assertIn(inactivo, form.fields["mantenimientos"].queryset)
        self.assertIn(inactivo.pk, form.initial["mantenimientos"])

    def test_rechaza_precio_negativo(self):
        form = ServicioForm(data=self.datos(precio_total="-1"))

        self.assertFalse(form.is_valid())
        self.assertIn("precio_total", form.errors)
