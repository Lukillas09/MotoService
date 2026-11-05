from decimal import Decimal, InvalidOperation
import unicodedata

from django import template


register = template.Library()


@register.filter
def miles(valor):
    if valor is None or valor == "":
        return ""
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return valor


@register.filter
def dinero(valor):
    if valor is None or valor == "":
        return ""
    try:
        numero = Decimal(str(valor))
        formato = f"{numero:,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return valor
    formato = formato.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"$ {formato}"


@register.filter
def estado_badge(estado):
    return {
        "ABIERTO": "status-badge status-info",
        "FINALIZADO": "status-badge status-success",
        "CANCELADO": "status-badge status-neutral",
    }.get(estado, "status-badge status-neutral")


@register.filter
def mantenimiento_badge(estado):
    valor = getattr(estado, "value", estado)
    return {
        "VENCIDO": "status-badge status-danger",
        "PROXIMO": "status-badge status-warning",
        "AL_DIA": "status-badge status-success",
        "SIN_REGISTRO": "status-badge status-neutral",
        "DATOS_INSUFICIENTES": "status-badge status-neutral",
    }.get(valor, "status-badge status-neutral")


@register.filter
def mantenimiento_tono(estado):
    valor = getattr(estado, "value", estado)
    return {
        "VENCIDO": "danger",
        "PROXIMO": "warning",
        "AL_DIA": "success",
        "SIN_REGISTRO": "secondary",
        "DATOS_INSUFICIENTES": "secondary",
    }.get(valor, "secondary")


@register.filter
def seguimiento_badge(estado):
    valor = getattr(estado, "value", estado)
    return {
        "PENDIENTE": "status-badge status-pending",
        "CONTACTADO": "status-badge status-info",
        "POSPUESTO": "status-badge status-purple",
        "TURNO_ACORDADO": "status-badge status-success",
        "NO_INTERESADO": "status-badge status-neutral",
    }.get(valor, "status-badge status-neutral")


@register.filter
def iniciales_usuario(usuario):
    """Iniciales de nombre y apellido (máximo 2); si faltan, la del username."""
    partes = (
        getattr(usuario, "first_name", ""),
        getattr(usuario, "last_name", ""),
    )
    iniciales = [
        unicodedata.normalize("NFC", parte.strip())[0].upper()[:1]
        for parte in partes
        if parte and parte.strip()
    ]
    if not iniciales:
        username = usuario.get_username() if hasattr(usuario, "get_username") else ""
        username = unicodedata.normalize("NFC", (username or "").strip())
        iniciales = [username[:1].upper()[:1]] if username else []
    return "".join(iniciales)
