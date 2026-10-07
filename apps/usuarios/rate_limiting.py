from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from math import ceil
from unicodedata import normalize

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LimiteAutenticacion
from .services import normalizar_email


SUJETO_IP_DESCONOCIDA = "ip-desconocida"


@dataclass(frozen=True)
class ReglaLimite:
    ambito: str
    sujeto: str
    max_intentos: int
    ventana_segundos: int


@dataclass(frozen=True)
class ReservaLimite:
    limite_id: int
    ventana_iniciada_en: datetime


@dataclass(frozen=True)
class ResultadoLimite:
    permitido: bool
    retry_after: int | None = None
    reservas: tuple[ReservaLimite, ...] = ()


def _normalizar_identificador(valor):
    return normalize("NFKC", (valor or "").strip()).casefold()


def _normalizar_ip(valor):
    try:
        direccion = ip_address((valor or "").strip())
    except ValueError:
        return None
    if direccion.version == 6:
        red = ip_network(f"{direccion}/64", strict=False)
        return f"{red.network_address.compressed}/64"
    return direccion.compressed


def obtener_ip_cliente(request):
    clave_principal = settings.AUTH_RATE_LIMIT_CLIENT_IP_META_KEY
    candidatos = (request.META.get(clave_principal), request.META.get("REMOTE_ADDR"))
    for candidato in candidatos:
        normalizada = _normalizar_ip(candidato)
        if normalizada:
            return normalizada
    return SUJETO_IP_DESCONOCIDA


def _hash_sujeto(ambito, sujeto):
    return salted_hmac(
        f"motoservice.rate_limit.{ambito}",
        sujeto,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def reglas_login(request):
    return (
        ReglaLimite(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IP,
            sujeto=obtener_ip_cliente(request),
            max_intentos=settings.AUTH_LOGIN_IP_MAX_ATTEMPTS,
            ventana_segundos=settings.AUTH_LOGIN_WINDOW_SECONDS,
        ),
        ReglaLimite(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IDENTIFICADOR,
            sujeto=_normalizar_identificador(request.POST.get("username")),
            max_intentos=settings.AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS,
            ventana_segundos=settings.AUTH_LOGIN_WINDOW_SECONDS,
        ),
    )


def reglas_password_reset(request):
    return (
        ReglaLimite(
            ambito=LimiteAutenticacion.Ambito.PASSWORD_RESET_IP,
            sujeto=obtener_ip_cliente(request),
            max_intentos=settings.PASSWORD_RESET_IP_MAX_ATTEMPTS,
            ventana_segundos=settings.PASSWORD_RESET_WINDOW_SECONDS,
        ),
        ReglaLimite(
            ambito=LimiteAutenticacion.Ambito.PASSWORD_RESET_EMAIL,
            sujeto=normalizar_email(request.POST.get("email")),
            max_intentos=settings.PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS,
            ventana_segundos=settings.PASSWORD_RESET_WINDOW_SECONDS,
        ),
    )


def _obtener_limite_bloqueado(regla, ahora):
    expira_en = ahora + timedelta(seconds=regla.ventana_segundos)
    limite, creado = (
        LimiteAutenticacion.objects.select_for_update().get_or_create(
            ambito=regla.ambito,
            sujeto_hash=_hash_sujeto(regla.ambito, regla.sujeto),
            defaults={
                "ventana_iniciada_en": ahora,
                "intentos": 0,
                "expira_en": expira_en,
            },
        )
    )
    if not creado and limite.expira_en <= ahora:
        limite.ventana_iniciada_en = ahora
        limite.intentos = 0
        limite.expira_en = expira_en
        limite.save(
            update_fields=("ventana_iniciada_en", "intentos", "expira_en")
        )
    return limite


@transaction.atomic
def consumir_limites(reglas, *, ahora=None):
    """Reserva un intento respetando el orden recibido: IP antes de identidad."""
    ahora = ahora or timezone.now()
    limites = []

    for regla in reglas:
        limite = _obtener_limite_bloqueado(regla, ahora)
        limites.append((limite, regla))
        if limite.intentos >= regla.max_intentos:
            retry_after = max(1, ceil((limite.expira_en - ahora).total_seconds()))
            return ResultadoLimite(permitido=False, retry_after=retry_after)

    reservas = []
    for limite, _regla in limites:
        limite.intentos += 1
        limite.save(update_fields=("intentos",))
        reservas.append(
            ReservaLimite(
                limite_id=limite.pk,
                ventana_iniciada_en=limite.ventana_iniciada_en,
            )
        )

    return ResultadoLimite(permitido=True, reservas=tuple(reservas))


def consumir_login(request):
    return consumir_limites(reglas_login(request))


def consumir_password_reset(request):
    return consumir_limites(reglas_password_reset(request))


@transaction.atomic
def devolver_reservas(reservas):
    """Descuenta solo las reservas de la misma ventana, sin borrar otros fallos."""
    for reserva in reservas:
        limite = (
            LimiteAutenticacion.objects.select_for_update()
            .filter(pk=reserva.limite_id)
            .first()
        )
        if (
            limite is not None
            and limite.ventana_iniciada_en == reserva.ventana_iniciada_en
            and limite.intentos > 0
        ):
            limite.intentos -= 1
            limite.save(update_fields=("intentos",))
