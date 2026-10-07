from dataclasses import dataclass
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.core.contacto import normalizar_numero_whatsapp
from apps.mantenimientos.models import TipoMantenimiento
from apps.mantenimientos.services import (
    EstadoMantenimiento,
    ResultadoMantenimiento,
    ResumenAlertas,
    construir_estados,
    obtener_resumen_alertas,
)
from apps.motos.models import Moto
from apps.motos.services import (
    PropietarioMotoCambioDuranteBloqueo,
    bloquear_cliente_actual_y_moto,
)

from .models import EventoSeguimientoMantenimiento, SeguimientoMantenimiento


class AlertaNoOperativa(Exception):
    pass


class AlertaObsoleta(Exception):
    pass


class AccionSeguimientoInvalida(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AlertaConSeguimiento:
    alerta_tecnica: ResultadoMantenimiento
    seguimiento: SeguimientoMantenimiento | None
    estado_seguimiento: str
    es_accionable: bool
    whatsapp_url: str | None
    telefono_disponible: bool
    posposicion_vencida: bool = False
    turno_vencido: bool = False

    @property
    def moto(self):
        return self.alerta_tecnica.moto

    @property
    def tipo_mantenimiento(self):
        return self.alerta_tecnica.tipo_mantenimiento

    @property
    def estado(self):
        return self.alerta_tecnica.estado

    @property
    def estado_label(self):
        return self.alerta_tecnica.estado_label

    @property
    def estado_seguimiento_label(self):
        return dict(SeguimientoMantenimiento.Estado.choices)[
            self.estado_seguimiento
        ]


@dataclass(frozen=True, slots=True)
class ResumenSeguimientos:
    resumen_tecnico: ResumenAlertas
    alertas: tuple[AlertaConSeguimiento, ...]
    accionables: tuple[AlertaConSeguimiento, ...]
    contactados: tuple[AlertaConSeguimiento, ...]
    pospuestos: tuple[AlertaConSeguimiento, ...]
    turnos: tuple[AlertaConSeguimiento, ...]
    no_interesados: tuple[AlertaConSeguimiento, ...]

    @property
    def vencidos(self):
        return self.resumen_tecnico.vencidos

    @property
    def proximos(self):
        return self.resumen_tecnico.proximos

    @property
    def hay_reglas(self):
        return self.resumen_tecnico.hay_reglas


@dataclass(frozen=True, slots=True)
class EstadoMotoConSeguimiento:
    estado_tecnico: ResultadoMantenimiento
    alerta_seguimiento: AlertaConSeguimiento | None

    @property
    def tipo_mantenimiento(self):
        return self.estado_tecnico.tipo_mantenimiento

    @property
    def estado(self):
        return self.estado_tecnico.estado


def _formatear_km(valor):
    return f"{int(valor):,}".replace(",", ".")


def construir_mensaje_whatsapp(alerta_tecnica, *, taller_nombre=None):
    cliente = alerta_tecnica.moto.cliente
    moto = alerta_tecnica.moto
    tipo = alerta_tecnica.tipo_mantenimiento.nombre.casefold()
    taller = str(
        (
            settings.TALLER_NOMBRE
            if taller_nombre is None
            else taller_nombre
        )
        or ""
    ).strip()

    lineas = [f"Hola {cliente.nombre}, ¿cómo estás?", ""]
    if taller:
        lineas.extend((f"Te contactamos desde {taller}.", ""))

    descripcion_moto = f"{moto.marca} {moto.modelo}"
    if alerta_tecnica.estado == EstadoMantenimiento.VENCIDO:
        lineas.append(
            "Según nuestro registro, tu "
            f"{descripcion_moto} ya se encuentra en fecha para el mantenimiento: "
            f"{tipo}."
        )
        cierre = "Si querés podemos coordinar para que la traigas al taller."
    else:
        lineas.append(
            "Según nuestro registro, tu "
            f"{descripcion_moto} está próxima a necesitar el mantenimiento: "
            f"{tipo}."
        )
        cierre = "Si querés podemos coordinar con tiempo."

    referencias = []
    if alerta_tecnica.proxima_fecha is not None:
        referencias.append(
            f"Fecha de referencia: {alerta_tecnica.proxima_fecha:%d/%m/%Y}."
        )
    if alerta_tecnica.proximo_km is not None:
        referencias.append(
            "Referencia de mantenimiento: "
            f"{_formatear_km(alerta_tecnica.proximo_km)} km."
        )
    if referencias:
        lineas.extend(("", *referencias))
    lineas.extend(("", cierre))
    return "\n".join(lineas)


def construir_url_whatsapp(alerta_tecnica):
    numero = normalizar_numero_whatsapp(alerta_tecnica.moto.cliente.telefono)
    if numero is None:
        return None
    mensaje = construir_mensaje_whatsapp(alerta_tecnica)
    return f"https://wa.me/{numero}?{urlencode({'text': mensaje})}"


def _crear_alerta_compuesta(alerta, seguimiento, *, hoy, ahora):
    if seguimiento is None:
        estado = SeguimientoMantenimiento.Estado.PENDIENTE
        accionable = True
        posposicion_vencida = False
        turno_vencido = False
    else:
        estado = seguimiento.estado
        posposicion_vencida = (
            estado == SeguimientoMantenimiento.Estado.POSPUESTO
            and seguimiento.pospuesto_hasta is not None
            and hoy >= seguimiento.pospuesto_hasta
        )
        turno_vencido = (
            estado == SeguimientoMantenimiento.Estado.TURNO_ACORDADO
            and seguimiento.turno_para is not None
            and ahora >= seguimiento.turno_para
        )
        accionable = (
            estado
            in {
                SeguimientoMantenimiento.Estado.PENDIENTE,
                SeguimientoMantenimiento.Estado.CONTACTADO,
            }
            or posposicion_vencida
            or turno_vencido
        )

    whatsapp_url = construir_url_whatsapp(alerta)
    return AlertaConSeguimiento(
        alerta_tecnica=alerta,
        seguimiento=seguimiento,
        estado_seguimiento=estado,
        es_accionable=accionable,
        whatsapp_url=whatsapp_url,
        telefono_disponible=whatsapp_url is not None,
        posposicion_vencida=posposicion_vencida,
        turno_vencido=turno_vencido,
    )


def superponer_seguimientos(alertas, *, hoy=None, ahora=None):
    hoy = hoy or timezone.localdate()
    ahora = ahora or timezone.now()
    alertas = tuple(alertas)
    claves = {
        (alerta.ultimo_mantenimiento.pk, alerta.moto.cliente_id)
        for alerta in alertas
        if alerta.ultimo_mantenimiento is not None
    }

    seguimientos_por_clave = {}
    if claves:
        mantenimientos_ids = {clave[0] for clave in claves}
        clientes_ids = {clave[1] for clave in claves}
        seguimientos = SeguimientoMantenimiento.objects.filter(
            mantenimiento_base_id__in=mantenimientos_ids,
            cliente_id__in=clientes_ids,
        ).select_related(
            "cliente",
            "mantenimiento_base",
            "ultimo_contacto_por",
            "actualizado_por",
        )
        seguimientos_por_clave = {
            (seguimiento.mantenimiento_base_id, seguimiento.cliente_id): seguimiento
            for seguimiento in seguimientos
        }

    return tuple(
        _crear_alerta_compuesta(
            alerta,
            seguimientos_por_clave.get(
                (
                    alerta.ultimo_mantenimiento.pk,
                    alerta.moto.cliente_id,
                )
            ),
            hoy=hoy,
            ahora=ahora,
        )
        for alerta in alertas
    )


def obtener_resumen_seguimientos(*, hoy=None, ahora=None):
    hoy = hoy or timezone.localdate()
    ahora = ahora or timezone.now()
    resumen_tecnico = obtener_resumen_alertas(hoy=hoy)
    alertas = superponer_seguimientos(
        resumen_tecnico.alertas,
        hoy=hoy,
        ahora=ahora,
    )
    return ResumenSeguimientos(
        resumen_tecnico=resumen_tecnico,
        alertas=alertas,
        accionables=tuple(alerta for alerta in alertas if alerta.es_accionable),
        contactados=tuple(
            alerta
            for alerta in alertas
            if alerta.estado_seguimiento
            == SeguimientoMantenimiento.Estado.CONTACTADO
        ),
        pospuestos=tuple(
            alerta
            for alerta in alertas
            if alerta.estado_seguimiento
            == SeguimientoMantenimiento.Estado.POSPUESTO
        ),
        turnos=tuple(
            alerta
            for alerta in alertas
            if alerta.estado_seguimiento
            == SeguimientoMantenimiento.Estado.TURNO_ACORDADO
        ),
        no_interesados=tuple(
            alerta
            for alerta in alertas
            if alerta.estado_seguimiento
            == SeguimientoMantenimiento.Estado.NO_INTERESADO
        ),
    )


def superponer_estados_moto(estados, *, hoy=None, ahora=None):
    estados = tuple(estados)
    operativos = tuple(
        estado
        for estado in estados
        if estado.estado
        in (EstadoMantenimiento.VENCIDO, EstadoMantenimiento.PROXIMO)
    )
    alertas = superponer_seguimientos(operativos, hoy=hoy, ahora=ahora)
    por_tipo = {
        alerta.tipo_mantenimiento.pk: alerta
        for alerta in alertas
    }
    return tuple(
        EstadoMotoConSeguimiento(
            estado_tecnico=estado,
            alerta_seguimiento=por_tipo.get(estado.tipo_mantenimiento.pk),
        )
        for estado in estados
    )


def obtener_alerta_operativa_actual(
    moto_id,
    tipo_id,
    *,
    hoy=None,
    bloquear=False,
):
    try:
        if bloquear:
            _cliente, moto = bloquear_cliente_actual_y_moto(moto_id)
            tipo = TipoMantenimiento.objects.select_for_update(no_key=True).get(
                pk=tipo_id
            )
        else:
            moto = Moto.objects.select_related("cliente").get(pk=moto_id)
            tipo = TipoMantenimiento.objects.get(pk=tipo_id)
    except (
        Moto.DoesNotExist,
        Cliente.DoesNotExist,
        TipoMantenimiento.DoesNotExist,
        PropietarioMotoCambioDuranteBloqueo,
    ) as error:
        raise AlertaNoOperativa("La alerta solicitada ya no existe.") from error

    if not moto.activo or not moto.cliente.activo:
        raise AlertaNoOperativa("La moto o su cliente actual ya no están activos.")
    if not tipo.activo or not tipo.genera_recordatorio:
        raise AlertaNoOperativa("La regla de mantenimiento ya no está activa.")

    alerta = construir_estados((moto,), (tipo,), hoy=hoy)[0]
    if alerta.estado not in (
        EstadoMantenimiento.VENCIDO,
        EstadoMantenimiento.PROXIMO,
    ) or alerta.ultimo_mantenimiento is None:
        raise AlertaNoOperativa(
            "El mantenimiento ya no requiere seguimiento operativo."
        )
    return alerta


def _registrar_accion(
    *,
    moto_id,
    tipo_id,
    mantenimiento_base_esperado_id,
    usuario,
    tipo_evento,
    estado=None,
    nota="",
    pospuesto_hasta=None,
    turno_para=None,
    hoy=None,
    ahora=None,
):
    hoy = hoy or timezone.localdate()
    ahora = ahora or timezone.now()
    nota = (nota or "").strip()

    with transaction.atomic():
        alerta = obtener_alerta_operativa_actual(
            moto_id,
            tipo_id,
            hoy=hoy,
            bloquear=True,
        )
        if alerta.ultimo_mantenimiento.pk != mantenimiento_base_esperado_id:
            raise AlertaObsoleta(
                "La alerta cambió porque se registró otro mantenimiento. "
                "Revisá el estado actualizado."
            )

        seguimiento, creado = (
            SeguimientoMantenimiento.objects.select_for_update(
                no_key=True
            ).get_or_create(
                mantenimiento_base=alerta.ultimo_mantenimiento,
                cliente=alerta.moto.cliente,
            )
        )
        if (
            tipo_evento == EventoSeguimientoMantenimiento.Tipo.REABIERTO
            and (
                creado
                or seguimiento.estado
                == SeguimientoMantenimiento.Estado.PENDIENTE
            )
        ):
            raise AlertaNoOperativa("Este seguimiento ya se encuentra pendiente.")

        if estado is not None:
            seguimiento.estado = estado
        seguimiento.actualizado_por = usuario
        if tipo_evento != EventoSeguimientoMantenimiento.Tipo.NOTA:
            seguimiento.pospuesto_hasta = None
            seguimiento.turno_para = None

        if tipo_evento == EventoSeguimientoMantenimiento.Tipo.CONTACTADO:
            seguimiento.ultimo_contacto_en = ahora
            seguimiento.ultimo_contacto_por = usuario
        elif tipo_evento == EventoSeguimientoMantenimiento.Tipo.POSPUESTO:
            seguimiento.pospuesto_hasta = pospuesto_hasta
        elif tipo_evento == EventoSeguimientoMantenimiento.Tipo.TURNO_ACORDADO:
            seguimiento.turno_para = turno_para

        if nota:
            seguimiento.observaciones = nota
        seguimiento.save()

        EventoSeguimientoMantenimiento.objects.create(
            seguimiento=seguimiento,
            tipo_evento=tipo_evento,
            usuario=usuario,
            nota=nota,
            pospuesto_hasta=pospuesto_hasta,
            turno_para=turno_para,
        )

    return _crear_alerta_compuesta(
        alerta,
        seguimiento,
        hoy=hoy,
        ahora=ahora,
    )


def marcar_contactado(**kwargs):
    return _registrar_accion(
        **kwargs,
        tipo_evento=EventoSeguimientoMantenimiento.Tipo.CONTACTADO,
        estado=SeguimientoMantenimiento.Estado.CONTACTADO,
    )


def posponer_seguimiento(*, pospuesto_hasta, **kwargs):
    hoy = kwargs.get("hoy") or timezone.localdate()
    if pospuesto_hasta is None or pospuesto_hasta <= hoy:
        raise AccionSeguimientoInvalida(
            "La fecha para recordar debe ser posterior a hoy."
        )
    return _registrar_accion(
        **kwargs,
        tipo_evento=EventoSeguimientoMantenimiento.Tipo.POSPUESTO,
        estado=SeguimientoMantenimiento.Estado.POSPUESTO,
        pospuesto_hasta=pospuesto_hasta,
    )


def acordar_turno(*, turno_para, **kwargs):
    ahora = kwargs.get("ahora") or timezone.now()
    if turno_para is None or timezone.is_naive(turno_para) or turno_para <= ahora:
        raise AccionSeguimientoInvalida(
            "El turno debe tener una fecha y hora futura."
        )
    return _registrar_accion(
        **kwargs,
        tipo_evento=EventoSeguimientoMantenimiento.Tipo.TURNO_ACORDADO,
        estado=SeguimientoMantenimiento.Estado.TURNO_ACORDADO,
        turno_para=turno_para,
    )


def marcar_no_interesado(**kwargs):
    return _registrar_accion(
        **kwargs,
        tipo_evento=EventoSeguimientoMantenimiento.Tipo.NO_INTERESADO,
        estado=SeguimientoMantenimiento.Estado.NO_INTERESADO,
    )


def reabrir_seguimiento(**kwargs):
    return _registrar_accion(
        **kwargs,
        tipo_evento=EventoSeguimientoMantenimiento.Tipo.REABIERTO,
        estado=SeguimientoMantenimiento.Estado.PENDIENTE,
    )


def agregar_nota(**kwargs):
    return _registrar_accion(
        **kwargs,
        tipo_evento=EventoSeguimientoMantenimiento.Tipo.NOTA,
    )
