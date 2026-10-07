"""Locks de dominio en orden Cliente → Moto → Servicio → Mantenimiento → Seguimiento."""

from apps.clientes.models import Cliente

from .models import Moto


class PropietarioMotoCambioDuranteBloqueo(Exception):
    """La relación cambió mientras se adquirían los locks en orden."""


def bloquear_cliente_actual_y_moto(moto_id):
    """Bloquea Cliente → Moto sin depender de locks implícitos por joins."""
    cliente_id = Moto.objects.values_list("cliente_id", flat=True).get(pk=moto_id)
    cliente = Cliente.objects.select_for_update(no_key=True).get(pk=cliente_id)
    moto = Moto.objects.select_for_update(no_key=True).get(pk=moto_id)

    if moto.cliente_id != cliente.pk:
        raise PropietarioMotoCambioDuranteBloqueo

    # Evita otra consulta y garantiza que las validaciones usen la fila bloqueada.
    moto.cliente = cliente
    return cliente, moto
