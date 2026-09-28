import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models.functions import Lower, Trim
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .roles import (
    GRUPO_PROPIETARIO,
    ROL_PROPIETARIO,
    es_propietario,
    puede_modificar_usuario,
    propietarios_activos,
)


logger = logging.getLogger(__name__)


def normalizar_email(email):
    return (email or "").strip().lower()


def validar_email_unico(email, *, excluir_pk=None):
    queryset = get_user_model().objects.annotate(
        email_normalizado=Lower(Trim("email"))
    ).filter(email_normalizado=normalizar_email(email))
    if excluir_pk is not None:
        queryset = queryset.exclude(pk=excluir_pk)
    if queryset.exists():
        raise ValidationError("Ya existe un usuario con este correo electrónico.")


def asignar_rol(usuario, rol):
    if usuario.is_superuser:
        return
    grupo, _creado = Group.objects.get_or_create(name=GRUPO_PROPIETARIO)
    if rol == ROL_PROPIETARIO:
        usuario.groups.add(grupo)
    else:
        usuario.groups.remove(grupo)


def _bloquear_gestion_propietarios():
    """Serializa cambios de rol/estado que podrían quitar al último dueño."""
    grupo, _creado = Group.objects.get_or_create(name=GRUPO_PROPIETARIO)
    Group.objects.select_for_update().get(pk=grupo.pk)


@transaction.atomic
def crear_usuario_invitado(datos):
    email = normalizar_email(datos["email"])
    validar_email_unico(email)
    usuario = get_user_model()(
        username=datos["username"].strip(),
        first_name=datos["first_name"].strip(),
        last_name=datos["last_name"].strip(),
        email=email,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    usuario.set_unusable_password()
    usuario.full_clean()
    usuario.save()
    asignar_rol(usuario, datos["rol"])
    return usuario


def _validar_actor(actor, objetivo):
    if not puede_modificar_usuario(actor, objetivo):
        raise PermissionDenied


def _validar_propietario_restante(objetivo, *, nuevo_rol=None, desactivar=False):
    deja_de_ser_propietario = nuevo_rol is not None and nuevo_rol != ROL_PROPIETARIO
    if objetivo.is_superuser:
        deja_de_ser_propietario = False
    if not (desactivar or deja_de_ser_propietario):
        return
    if objetivo.is_active and es_propietario(objetivo):
        hay_otro = propietarios_activos().exclude(pk=objetivo.pk).exists()
        if not hay_otro:
            raise ValidationError(
                "No podés dejar el taller sin al menos un Propietario activo."
            )


@transaction.atomic
def actualizar_usuario(actor, objetivo, datos):
    _bloquear_gestion_propietarios()
    objetivo = (
        get_user_model()
        .objects.select_for_update()
        .prefetch_related("groups")
        .get(pk=objetivo.pk)
    )
    _validar_actor(actor, objetivo)
    validar_email_unico(datos["email"], excluir_pk=objetivo.pk)
    _validar_propietario_restante(objetivo, nuevo_rol=datos["rol"])

    email = normalizar_email(datos["email"])
    email_cambio = email != normalizar_email(objetivo.email)
    pendiente = not objetivo.has_usable_password()
    objetivo.username = datos["username"].strip()
    objetivo.first_name = datos["first_name"].strip()
    objetivo.last_name = datos["last_name"].strip()
    objetivo.email = email
    if pendiente and email_cambio:
        objetivo.set_unusable_password()
    objetivo.full_clean()
    objetivo.save()
    asignar_rol(objetivo, datos["rol"])
    return objetivo, pendiente and email_cambio


@transaction.atomic
def desactivar_usuario(actor, usuario_pk):
    _bloquear_gestion_propietarios()
    objetivo = (
        get_user_model()
        .objects.select_for_update()
        .prefetch_related("groups")
        .get(pk=usuario_pk)
    )
    _validar_actor(actor, objetivo)
    _validar_propietario_restante(objetivo, desactivar=True)
    if objetivo.is_active:
        objetivo.is_active = False
        objetivo.save(update_fields=("is_active",))
    return objetivo


@transaction.atomic
def reactivar_usuario(actor, usuario_pk):
    objetivo = get_user_model().objects.select_for_update().get(pk=usuario_pk)
    _validar_actor(actor, objetivo)
    if not objetivo.is_active:
        objetivo.is_active = True
        objetivo.save(update_fields=("is_active",))
    return objetivo


@transaction.atomic
def preparar_reenvio_invitacion(actor, usuario_pk):
    objetivo = get_user_model().objects.select_for_update().get(pk=usuario_pk)
    _validar_actor(actor, objetivo)
    if not objetivo.is_active:
        raise ValidationError("Primero reactivá el usuario para reenviar la invitación.")
    if objetivo.has_usable_password():
        raise ValidationError("Este usuario ya configuró su contraseña.")
    if not objetivo.email:
        raise ValidationError("El usuario necesita un correo para recibir la invitación.")
    objetivo.set_unusable_password()
    objetivo.save(update_fields=("password",))
    return objetivo


def construir_enlace_invitacion(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    ruta = reverse(
        "password_reset_confirm",
        kwargs={"uidb64": uid, "token": token},
    )
    return request.build_absolute_uri(ruta)


def enviar_invitacion(usuario, request):
    enlace = construir_enlace_invitacion(request, usuario)
    contexto = {
        "usuario": usuario,
        "enlace": enlace,
        "taller_nombre": settings.TALLER_NOMBRE,
    }
    asunto = render_to_string(
        "registration/invitacion_asunto.txt", contexto
    ).strip().replace("\n", " ")
    texto = render_to_string("registration/invitacion_email.txt", contexto)
    html = render_to_string("registration/invitacion_email.html", contexto)
    mensaje = EmailMultiAlternatives(
        asunto,
        texto,
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email],
    )
    mensaje.attach_alternative(html, "text/html")
    mensaje.send(fail_silently=False)


def intentar_enviar_invitacion(usuario, request):
    try:
        enviar_invitacion(usuario, request)
    except Exception as error:  # El proveedor de email puede fallar de varias formas.
        logger.warning(
            "No se pudo enviar una invitación. usuario_id=%s error_type=%s",
            usuario.pk,
            type(error).__name__,
        )
        return False
    return True
