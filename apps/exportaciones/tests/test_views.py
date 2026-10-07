import codecs
import csv
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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
from apps.usuarios.roles import GRUPO_PROPIETARIO


ENDPOINTS_EXPORTACION = (
    "exportaciones:index",
    "exportaciones:backup_instructions",
    "exportaciones:clientes_csv",
    "exportaciones:motos_csv",
    "exportaciones:servicios_csv",
    "exportaciones:mantenimientos_csv",
    "exportaciones:tipos_mantenimiento_csv",
    "exportaciones:seguimientos_csv",
    "exportaciones:eventos_seguimiento_csv",
    "exportaciones:completo_xlsx",
)


class ExportacionesViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="lucas",
            password="clave-segura",
            email="lucas@example.com",
        )
        cls.propietario = get_user_model().objects.create_user(
            username="dueno-exportaciones",
            password="clave-segura",
            email="dueno-exportaciones@example.com",
        )
        grupo = Group.objects.create(name=GRUPO_PROPIETARIO)
        cls.propietario.groups.add(grupo)
        cls.superuser = get_user_model().objects.create_superuser(
            username="admin-exportaciones",
            password="clave-segura",
            email="admin-exportaciones@example.com",
        )
        cls.carlos = Cliente.objects.create(
            nombre="Carlos",
            apellido="González",
            telefono="260 4123456",
            email="carlos@example.com",
        )
        cls.martin = Cliente.objects.create(nombre="Martín", apellido="Pérez")
        cls.archivado = Cliente.objects.create(nombre="Archivado")
        cls.moto = Moto.objects.create(
            cliente=cls.carlos,
            patente="AF123XY",
            marca="Honda",
            modelo="Tornado",
            kilometraje_actual=15000,
        )
        cls.moto_archivada = Moto.objects.create(
            cliente=cls.archivado,
            marca="Yamaha",
            modelo="YBR",
            activo=False,
        )
        cls.archivado.activo = False
        cls.archivado.save(update_fields=("activo",))
        cls.servicio = Servicio.objects.create(
            moto=cls.moto,
            fecha=date(2026, 9, 1),
            kilometraje=14000,
            precio_total=Decimal("75000.10"),
            trabajos_adicionales="Ajuste general",
            observaciones="Revisar transmisión",
            creado_por=cls.usuario,
        )
        cls.tipo = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        cls.realizado = MantenimientoRealizado.objects.create(
            servicio=cls.servicio,
            tipo_mantenimiento=cls.tipo,
            observaciones="Aceite sintético",
        )
        cls.seguimiento = SeguimientoMantenimiento.objects.create(
            mantenimiento_base=cls.realizado,
            cliente=cls.carlos,
            estado=SeguimientoMantenimiento.Estado.CONTACTADO,
            ultimo_contacto_en=timezone.now(),
            ultimo_contacto_por=cls.usuario,
            actualizado_por=cls.usuario,
            observaciones="Respondió por WhatsApp",
        )
        cls.evento = EventoSeguimientoMantenimiento.objects.create(
            seguimiento=cls.seguimiento,
            tipo_evento=EventoSeguimientoMantenimiento.Tipo.CONTACTADO,
            usuario=cls.usuario,
            nota="Cliente avisado",
        )
        cls.moto.cliente = cls.martin
        cls.moto.save()

    def _leer_csv(self, nombre_url):
        response = self.client.get(reverse(nombre_url))
        contenido = response.content.decode("utf-8-sig")
        filas = list(csv.reader(StringIO(contenido), delimiter=";"))
        return response, filas

    def _fila_por_id(self, filas, identificador):
        encabezados = filas[0]
        for fila in filas[1:]:
            if fila[0] == str(identificador):
                return dict(zip(encabezados, fila, strict=True))
        self.fail(f"No se encontró la fila {identificador}.")

    def test_toda_la_interfaz_y_las_descargas_requieren_login(self):
        for nombre in ENDPOINTS_EXPORTACION:
            with self.subTest(nombre=nombre):
                url = reverse(nombre)
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('login')}?next={url}",
                )

    def test_usuario_normal_recibe_403_en_cada_endpoint(self):
        self.client.force_login(self.usuario)

        for nombre in ENDPOINTS_EXPORTACION:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_propietario_y_superuser_acceden_a_cada_endpoint(self):
        for usuario in (self.propietario, self.superuser):
            self.client.force_login(usuario)
            for nombre in ENDPOINTS_EXPORTACION:
                with self.subTest(usuario=usuario.username, nombre=nombre):
                    self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_navegacion_desktop_y_mobile_oculta_exportaciones_al_usuario(self):
        url = reverse("exportaciones:index")
        self.client.force_login(self.usuario)

        contenido = self.client.get(reverse("core:dashboard")).content.decode()
        sidebar = contenido.split('<nav class="sidebar-nav">')[1].split("</nav>")[0]
        mobile = contenido.split('<nav class="mobile-more-nav">')[1].split(
            "</nav>"
        )[0]
        for navegacion in (sidebar, mobile):
            self.assertNotIn(f'href="{url}"', navegacion)

        self.client.force_login(self.propietario)
        contenido = self.client.get(reverse("core:dashboard")).content.decode()
        sidebar = contenido.split('<nav class="sidebar-nav">')[1].split("</nav>")[0]
        mobile = contenido.split('<nav class="mobile-more-nav">')[1].split(
            "</nav>"
        )[0]
        for navegacion in (sidebar, mobile):
            self.assertIn(f'href="{url}"', navegacion)

    def test_pantalla_principal_muestra_todas_las_descargas(self):
        self.client.force_login(self.propietario)

        response = self.client.get(reverse("exportaciones:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Datos y exportaciones")
        self.assertContains(response, "Descargar CSV", count=7)
        self.assertContains(response, "Descargar Excel completo")
        self.assertContains(response, "No reemplazan un backup")

    def test_cada_csv_tiene_headers_seguros_bom_y_fila_esperada(self):
        self.client.force_login(self.propietario)
        casos = (
            ("exportaciones:clientes_csv", "Nombre", "Carlos"),
            ("exportaciones:motos_csv", "Patente", "AF123XY"),
            ("exportaciones:servicios_csv", "ID servicio", str(self.servicio.pk)),
            ("exportaciones:mantenimientos_csv", "Servicio ID", str(self.servicio.pk)),
            ("exportaciones:tipos_mantenimiento_csv", "Nombre", "Cambio de aceite"),
            ("exportaciones:seguimientos_csv", "Cliente contactado", "Carlos González"),
            ("exportaciones:eventos_seguimiento_csv", "Tipo evento", "Contactado"),
        )

        for nombre, encabezado, valor in casos:
            with self.subTest(nombre=nombre):
                response, filas = self._leer_csv(nombre)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
                self.assertIn("attachment;", response["Content-Disposition"])
                self.assertIn(".csv", response["Content-Disposition"])
                self.assertIn("private", response["Cache-Control"])
                self.assertIn("no-store", response["Cache-Control"])
                self.assertTrue(response.content.startswith(codecs.BOM_UTF8))
                self.assertIn(encabezado, filas[0])
                self.assertTrue(any(valor in fila for fila in filas[1:]))

    def test_csv_incluye_clientes_y_motos_archivados(self):
        self.client.force_login(self.propietario)

        _, clientes = self._leer_csv("exportaciones:clientes_csv")
        _, motos = self._leer_csv("exportaciones:motos_csv")

        fila_cliente = self._fila_por_id(clientes, self.archivado.pk)
        fila_moto = self._fila_por_id(motos, self.moto_archivada.pk)
        self.assertEqual(fila_cliente["Activo"], "No")
        self.assertEqual(fila_moto["Activa"], "No")

    def test_csv_servicios_conserva_cliente_historico(self):
        self.client.force_login(self.propietario)

        _, servicios = self._leer_csv("exportaciones:servicios_csv")
        _, motos = self._leer_csv("exportaciones:motos_csv")

        fila_servicio = self._fila_por_id(servicios, self.servicio.pk)
        fila_moto = self._fila_por_id(motos, self.moto.pk)
        self.assertEqual(fila_servicio["Cliente histórico"], "Carlos González")
        self.assertEqual(fila_moto["Cliente actual"], "Martín Pérez")

    def test_csv_seguimientos_conserva_cliente_contactado(self):
        self.client.force_login(self.propietario)

        _, seguimientos = self._leer_csv("exportaciones:seguimientos_csv")

        fila = self._fila_por_id(seguimientos, self.seguimiento.pk)
        self.assertEqual(fila["Cliente contactado"], "Carlos González")
        self.assertNotEqual(fila["Cliente contactado"], self.moto.cliente.nombre_completo)

    def test_csv_neutraliza_formulas_sin_modificar_la_base(self):
        cliente = Cliente.objects.create(
            nombre="=2+2",
            telefono="-2604000000",
            observaciones="@SUM(A1:A2)",
        )
        moto = Moto.objects.create(
            cliente=cliente,
            marca="+cmd",
            modelo="Modelo",
        )
        self.client.force_login(self.propietario)

        _, clientes = self._leer_csv("exportaciones:clientes_csv")
        _, motos = self._leer_csv("exportaciones:motos_csv")

        fila_cliente = self._fila_por_id(clientes, cliente.pk)
        fila_moto = self._fila_por_id(motos, moto.pk)
        self.assertEqual(fila_cliente["Nombre"], "'=2+2")
        self.assertEqual(fila_cliente["Teléfono"], "'-2604000000")
        self.assertEqual(fila_cliente["Observaciones"], "'@SUM(A1:A2)")
        self.assertEqual(fila_moto["Marca"], "'+cmd")
        cliente.refresh_from_db()
        moto.refresh_from_db()
        self.assertEqual(cliente.nombre, "=2+2")
        self.assertEqual(moto.marca, "+cmd")

    def test_descarga_excel_tiene_content_type_filename_y_no_store(self):
        self.client.force_login(self.propietario)

        response = self.client.get(reverse("exportaciones:completo_xlsx"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("motoservice_exportacion_", response["Content-Disposition"])
        self.assertIn(".xlsx", response["Content-Disposition"])
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(response.content.startswith(b"PK"))

    def test_pagina_de_backup_no_ejecuta_backup_desde_http(self):
        self.client.force_login(self.propietario)

        response = self.client.get(reverse("exportaciones:backup_instructions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fuera del navegador")
        self.assertContains(response, "python manage.py backup_database")
