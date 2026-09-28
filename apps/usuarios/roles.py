from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q


GRUPO_PROPIETARIO = "Propietario"
ROL_PROPIETARIO = "PROPIETARIO"
ROL_USUARIO = "USUARIO"


def es_propietario(usuario):
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.is_superuser:
        return True

    grupos_precargados = getattr(usuario, "_prefetched_objects_cache", {}).get(
        "groups"
    )
    if grupos_precargados is not None:
        return any(grupo.name == GRUPO_PROPIETARIO for grupo in grupos_precargados)
    return usuario.groups.filter(name=GRUPO_PROPIETARIO).exists()


def rol_de_usuario(usuario):
    return ROL_PROPIETARIO if es_propietario(usuario) else ROL_USUARIO


def propietarios_activos():
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(groups__name=GRUPO_PROPIETARIO))
        .distinct()
    )


def es_ultimo_propietario_activo(usuario):
    return (
        usuario.is_active
        and es_propietario(usuario)
        and not propietarios_activos().exclude(pk=usuario.pk).exists()
    )


def puede_modificar_usuario(actor, objetivo):
    if not es_propietario(actor):
        return False
    if objetivo.is_superuser and not actor.is_superuser:
        return False
    return True


def propietario_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not es_propietario(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped

