import html
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.mantenimientos.models import MantenimientoRealizado, TipoMantenimiento
from apps.motos.models import Moto
from apps.servicios.models import Servicio


def atributos_del_form(response, action):
    """Atributos del <form> que apunta a ``action``, con entidades decodificadas."""
    contenido = response.content.decode("utf-8")
    etiqueta = re.search(rf'<form\b[^>]*action="{re.escape(action)}"[^>]*>', contenido)
    assert etiqueta, f"No hay form hacia {action}"
    return {
        nombre: html.unescape(valor)
        for nombre, valor in re.findall(r'([\w-]+)="([^"]*)"', etiqueta.group(0))
    }


class ConfirmacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.propietario = User.objects.create_superuser(
            username="duenio", password="clave-segura", email="duenio@example.test"
        )
        cls.pendiente = User.objects.create_user(username="invitada", email="invitada@example.test")
        cls.pendiente.set_unusable_password()
        cls.pendiente.save()
        cls.cliente = Cliente.objects.create(nombre="Carlos", apellido="López", telefono="2604123456")
        cls.moto = Moto.objects.create(
            cliente=cls.cliente, marca="Honda", modelo="Wave", kilometraje_actual=20000
        )
        cls.tipo = TipoMantenimiento.objects.get(nombre="Cambio de aceite")
        cls.tipo.activo = True
        cls.tipo.genera_recordatorio = True
        cls.tipo.intervalo_meses = None
        cls.tipo.intervalo_km = 5000
        cls.tipo.aviso_km = 500
        cls.tipo.save()
        cls.servicio = Servicio.objects.create(
            moto=cls.moto,
            fecha=timezone.localdate() - timedelta(days=30),
            kilometraje=10000,
        )
        MantenimientoRealizado.objects.create(servicio=cls.servicio, tipo_mantenimiento=cls.tipo)

    def setUp(self):
        self.client.force_login(self.propietario)

    def assertConfirmacion(self, url, action, titulo, boton, tono, consecuencia):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        atributos = atributos_del_form(response, action)
        self.assertEqual(atributos["data-confirm-title"], titulo)
        self.assertEqual(atributos["data-confirm-button"], boton)
        self.assertEqual(atributos["data-confirm-tone"], tono)
        self.assertIn(consecuencia, atributos["data-confirm-message"])
        self.assertEqual(atributos["method"], "post")

    def test_archivar_cliente(self):
        self.assertConfirmacion(
            reverse("clientes:detail", args=(self.cliente.pk,)),
            reverse("clientes:archive", args=(self.cliente.pk,)),
            "¿Archivar este cliente?",
            "Archivar cliente",
            "danger",
            "Podés restaurarlo después.",
        )

    def test_archivar_moto(self):
        self.assertConfirmacion(
            reverse("motos:detail", args=(self.moto.pk,)),
            reverse("motos:archive", args=(self.moto.pk,)),
            "¿Archivar esta moto?",
            "Archivar moto",
            "danger",
            "podés restaurarla después.",
        )

    def test_cancelar_servicio(self):
        self.assertConfirmacion(
            reverse("servicios:detail", args=(self.servicio.pk,)),
            reverse("servicios:cancel", args=(self.servicio.pk,)),
            "¿Cancelar este servicio?",
            "Cancelar servicio",
            "danger",
            "sigue visible en el historial",
        )

    def test_desactivar_y_reenviar_invitacion(self):
        lista = reverse("usuarios:list")
        self.assertConfirmacion(
            lista,
            reverse("usuarios:deactivate", args=(self.pendiente.pk,)),
            "¿Desactivar a invitada?",
            "Desactivar usuario",
            "danger",
            "No va a poder ingresar hasta que lo reactives.",
        )
        self.assertConfirmacion(
            lista,
            reverse("usuarios:resend_invitation", args=(self.pendiente.pk,)),
            "¿Reenviar la invitación?",
            "Reenviar invitación",
            "primary",
            "el anterior deja de funcionar",
        )

    def test_desactivar_tipo_de_mantenimiento(self):
        self.assertConfirmacion(
            reverse("mantenimientos:configuracion"),
            reverse("mantenimientos:tipo_archive", args=(self.tipo.pk,)),
            "¿Desactivar este tipo de mantenimiento?",
            "Desactivar tipo",
            "warning",
            "podés restaurarlo después.",
        )

    def test_marcar_no_interesado(self):
        self.assertConfirmacion(
            reverse("notificaciones:alertas"),
            reverse("notificaciones:no_interesado", args=(self.moto.pk, self.tipo.pk)),
            "¿Marcar como no interesado?",
            "Marcar no interesado",
            "warning",
            "podés reabrir el seguimiento",
        )

    def test_modal_unico_y_accesible_en_el_shell_autenticado(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertContains(response, 'id="confirm-modal"', count=1)
        self.assertContains(response, 'aria-labelledby="confirm-modal-title"')
        self.assertContains(response, 'aria-describedby="confirm-modal-message"')
        self.assertContains(response, 'id="confirm-modal-title"')
        self.assertContains(response, 'id="confirm-modal-message"')
        self.assertContains(response, "data-confirm-cancel")
        self.assertContains(response, "data-confirm-accept")

    def test_pantallas_publicas_no_incluyen_el_modal(self):
        self.client.logout()

        response = self.client.get(reverse("login"))

        self.assertNotContains(response, 'id="confirm-modal"')
