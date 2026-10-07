from django.core.exceptions import ValidationError
from django.db import transaction

from apps.mantenimientos.models import MantenimientoRealizado


@transaction.atomic
def guardar_servicio_y_mantenimientos(
    servicio,
    tipos_mantenimiento,
    *,
    creado_por=None,
):
    if servicio._state.adding and creado_por and creado_por.is_authenticated:
        servicio.creado_por = creado_por

    servicio.save()

    tipos_ids = {tipo.pk for tipo in tipos_mantenimiento}
    realizaciones = list(
        MantenimientoRealizado.objects.select_for_update(
            of=("self",),
        )
        .filter(servicio=servicio)
        .select_related("tipo_mantenimiento")
        .order_by("pk")
    )
    realizaciones_a_eliminar = [
        realizacion
        for realizacion in realizaciones
        if realizacion.tipo_mantenimiento_id not in tipos_ids
    ]
    ids_a_eliminar = [realizacion.pk for realizacion in realizaciones_a_eliminar]
    ids_con_seguimiento = set(
        MantenimientoRealizado.objects.filter(
            pk__in=ids_a_eliminar,
            seguimientos__isnull=False,
        ).values_list("pk", flat=True)
    )
    if ids_con_seguimiento:
        nombres = ", ".join(
            realizacion.tipo_mantenimiento.nombre
            for realizacion in realizaciones_a_eliminar
            if realizacion.pk in ids_con_seguimiento
        )
        raise ValidationError(
            {
                "mantenimientos": (
                    "No se pueden quitar mantenimientos con seguimiento de contacto "
                    f"asociado: {nombres}. El seguimiento y su historial deben conservarse."
                )
            }
        )

    if ids_a_eliminar:
        MantenimientoRealizado.objects.filter(pk__in=ids_a_eliminar).delete()

    existentes = {
        realizacion.tipo_mantenimiento_id
        for realizacion in realizaciones
        if realizacion.tipo_mantenimiento_id in tipos_ids
    }
    MantenimientoRealizado.objects.bulk_create(
        [
            MantenimientoRealizado(
                servicio=servicio,
                tipo_mantenimiento_id=tipo_id,
            )
            for tipo_id in tipos_ids - existentes
        ]
    )
    return servicio
