from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.motos.models import Moto, normalizar_patente


class MotoModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nombre="Carlos", apellido="González")

    def test_creacion_y_representacion_con_patente(self):
        moto = Moto.objects.create(
            cliente=self.cliente,
            patente="af-123 xy",
            marca="  Honda ",
            modelo=" Tornado   XR250 ",
        )

        self.assertEqual(moto.patente, "AF123XY")
        self.assertEqual(moto.marca, "Honda")
        self.assertEqual(moto.modelo, "Tornado XR250")
        self.assertEqual(str(moto), "Honda Tornado XR250 — AF123XY")

    def test_representacion_sin_patente(self):
        moto = Moto.objects.create(
            cliente=self.cliente, marca="Honda", modelo="CRF"
        )

        self.assertEqual(str(moto), "Honda CRF")

    def test_normalizacion_de_patente_esta_centralizada(self):
        self.assertEqual(normalizar_patente(" af-123 xy "), "AF123XY")
        self.assertIsNone(normalizar_patente(" -  - "))

    def test_patente_duplicada_es_invalida_despues_de_normalizar(self):
        Moto.objects.create(
            cliente=self.cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
        )

        with self.assertRaises(ValidationError) as error:
            Moto.objects.create(
                cliente=self.cliente,
                patente="af-123-xy",
                marca="Yamaha",
                modelo="FZ",
            )

        self.assertIn("patente", error.exception.message_dict)

    def test_varias_motos_pueden_no_tener_patente(self):
        primera = Moto.objects.create(
            cliente=self.cliente, patente="", marca="Honda", modelo="CRF"
        )
        segunda = Moto.objects.create(
            cliente=self.cliente, patente=None, marca="Yamaha", modelo="YZ"
        )

        self.assertIsNone(primera.patente)
        self.assertIsNone(segunda.patente)

    def test_anio_actual_y_siguiente_son_validos(self):
        actual = timezone.localdate().year

        for anio in (actual, actual + 1):
            with self.subTest(anio=anio):
                moto = Moto(
                    cliente=self.cliente,
                    marca="Honda",
                    modelo="Wave",
                    anio=anio,
                )
                moto.full_clean()

    def test_anio_fuera_de_rango_es_invalido(self):
        for anio in (1899, timezone.localdate().year + 2):
            with self.subTest(anio=anio), self.assertRaises(ValidationError):
                Moto.objects.create(
                    cliente=self.cliente,
                    marca="Honda",
                    modelo="Wave",
                    anio=anio,
                )

    def test_kilometraje_y_cilindrada_no_aceptan_negativos(self):
        casos = (
            {"kilometraje_actual": -1},
            {"cilindrada_cc": -1},
        )

        for datos in casos:
            with self.subTest(datos=datos), self.assertRaises(ValidationError):
                Moto.objects.create(
                    cliente=self.cliente,
                    marca="Honda",
                    modelo="Wave",
                    **datos,
                )

    def test_instancia_obsoleta_no_puede_reducir_kilometraje(self):
        moto = Moto.objects.create(
            cliente=self.cliente,
            marca="Honda",
            modelo="Wave",
            kilometraje_actual=12000,
        )
        instancia_obsoleta = Moto.objects.get(pk=moto.pk)
        Moto.objects.filter(pk=moto.pk).update(kilometraje_actual=15000)

        instancia_obsoleta.kilometraje_actual = 13000
        with self.assertRaises(ValidationError) as contexto:
            instancia_obsoleta.save()

        self.assertIn("kilometraje_actual", contexto.exception.message_dict)
        moto.refresh_from_db()
        self.assertEqual(moto.kilometraje_actual, 15000)

    def test_update_parcial_obsoleto_no_sobrescribe_kilometraje(self):
        moto = Moto.objects.create(
            cliente=self.cliente,
            marca="Honda",
            modelo="Wave",
            kilometraje_actual=12000,
        )
        instancia_obsoleta = Moto.objects.get(pk=moto.pk)
        Moto.objects.filter(pk=moto.pk).update(kilometraje_actual=15000)

        instancia_obsoleta.activo = False
        instancia_obsoleta.save(update_fields=("activo", "actualizado_en"))

        moto.refresh_from_db()
        self.assertFalse(moto.activo)
        self.assertEqual(moto.kilometraje_actual, 15000)

    def test_no_crea_moto_para_cliente_archivado_por_orm(self):
        self.cliente.activo = False
        self.cliente.save(update_fields=("activo", "actualizado_en"))

        with self.assertRaises(ValidationError) as contexto:
            Moto.objects.create(
                cliente=self.cliente,
                marca="Honda",
                modelo="Wave",
            )

        self.assertIn("cliente", contexto.exception.message_dict)
        self.assertFalse(Moto.objects.exists())

    def test_cliente_es_obligatorio(self):
        moto = Moto(marca="Honda", modelo="Wave")

        with self.assertRaises(ValidationError) as error:
            moto.full_clean()

        self.assertIn("cliente", error.exception.message_dict)

    def test_guardar_sin_cliente_conserva_error_de_validacion(self):
        with self.assertRaises(ValidationError) as error:
            Moto.objects.create(marca="Honda", modelo="Wave")

        self.assertIn("cliente", error.exception.message_dict)

    def test_busqueda_por_patente_y_telefono_del_cliente(self):
        self.cliente.telefono = "+54 9 260 4123456"
        self.cliente.save()
        moto = Moto.objects.create(
            cliente=self.cliente,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
        )

        self.assertQuerySetEqual(Moto.objects.buscar("af-123-xy"), [moto])
        self.assertQuerySetEqual(Moto.objects.buscar("2604"), [moto])
        self.assertQuerySetEqual(Moto.objects.buscar("Honda Tornado"), [moto])
