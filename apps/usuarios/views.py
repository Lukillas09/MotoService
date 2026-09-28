from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.db.models.functions import Lower, Trim
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import (
    CambiarContrasenaForm,
    MiCuentaForm,
    NuevaContrasenaForm,
    RecuperarContrasenaForm,
    UsuarioCreateForm,
    UsuarioUpdateForm,
)
from .roles import (
    ROL_PROPIETARIO,
    es_propietario,
    propietario_required,
    puede_modificar_usuario,
    rol_de_usuario,
)
from .services import (
    actualizar_usuario,
    crear_usuario_invitado,
    desactivar_usuario,
    intentar_enviar_invitacion,
    preparar_reenvio_invitacion,
    reactivar_usuario,
)


User = get_user_model()


def _agregar_error_formulario(form, error):
    if hasattr(error, "error_dict"):
        for campo, errores in error.error_dict.items():
            destino = campo if campo in form.fields else None
            for item in errores:
                form.add_error(destino, item)
        return
    for mensaje in error.messages:
        form.add_error(None, mensaje)


def _estado_usuario(usuario):
    if not usuario.is_active:
        return "INACTIVO", "Inactivo", "secondary"
    if not usuario.has_usable_password():
        return "PENDIENTE", "Invitación pendiente", "warning"
    return "ACTIVO", "Activo", "success"


@propietario_required
def lista_usuarios(request):
    usuarios = list(User.objects.prefetch_related("groups").order_by("last_name", "first_name", "username"))
    propietarios_activos_ids = {
        usuario.pk
        for usuario in usuarios
        if usuario.is_active and es_propietario(usuario)
    }
    filas = []
    for usuario in usuarios:
        codigo_estado, estado, tono = _estado_usuario(usuario)
        filas.append(
            {
                "usuario": usuario,
                "rol": "Propietario"
                if rol_de_usuario(usuario) == ROL_PROPIETARIO
                else "Usuario",
                "estado_codigo": codigo_estado,
                "estado": estado,
                "tono": tono,
                "puede_gestionar": (
                    not usuario.is_superuser or request.user.is_superuser
                ),
                "ultimo_propietario": (
                    usuario.pk in propietarios_activos_ids
                    and len(propietarios_activos_ids) == 1
                ),
            }
        )

    duplicados = (
        User.objects.annotate(email_normalizado=Lower(Trim("email")))
        .exclude(email_normalizado="")
        .values("email_normalizado")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
        .count()
    )
    return render(
        request,
        "usuarios/list.html",
        {"filas": filas, "grupos_email_duplicado": duplicados},
    )


@propietario_required
def crear_usuario(request):
    form = UsuarioCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            usuario = crear_usuario_invitado(form.cleaned_data)
        except ValidationError as error:
            _agregar_error_formulario(form, error)
        else:
            if intentar_enviar_invitacion(usuario, request):
                messages.success(
                    request,
                    "Usuario creado. Enviamos una invitación a su correo.",
                )
            else:
                messages.warning(
                    request,
                    "El usuario fue creado, pero no pudimos enviar la invitación. Podés reenviarla.",
                )
            return redirect("usuarios:list")
    return render(
        request,
        "shared/model_form.html",
        {
            "form": form,
            "titulo": "Nuevo usuario",
            "descripcion": "Creá el acceso sin establecer ni conocer su contraseña.",
            "texto_boton": "Crear y enviar invitación",
            "cancel_url": "usuarios:list",
        },
    )


@propietario_required
def editar_usuario(request, pk):
    usuario = get_object_or_404(User.objects.prefetch_related("groups"), pk=pk)
    if not puede_modificar_usuario(request.user, usuario):
        raise PermissionDenied
    form = UsuarioUpdateForm(
        request.POST or None,
        instance=usuario,
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            usuario, debe_invitar = actualizar_usuario(
                request.user, usuario, form.cleaned_data
            )
        except ValidationError as error:
            _agregar_error_formulario(form, error)
        else:
            if debe_invitar:
                if intentar_enviar_invitacion(usuario, request):
                    messages.success(
                        request,
                        "Usuario actualizado. Enviamos una nueva invitación a su correo.",
                    )
                else:
                    messages.warning(
                        request,
                        "Usuario actualizado, pero no pudimos enviar la invitación. Podés reenviarla.",
                    )
            else:
                messages.success(request, "Usuario actualizado.")
            return redirect("usuarios:list")
    return render(
        request,
        "shared/model_form.html",
        {
            "form": form,
            "titulo": "Editar usuario",
            "descripcion": f"Actualizá el acceso de {usuario.get_username()}.",
            "texto_boton": "Guardar cambios",
            "cancel_url": "usuarios:list",
        },
    )


@propietario_required
@require_POST
def desactivar(request, pk):
    try:
        usuario = desactivar_usuario(request.user, pk)
    except User.DoesNotExist as error:
        raise Http404 from error
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("usuarios:list")

    es_usuario_actual = usuario.pk == request.user.pk
    if es_usuario_actual:
        logout(request)
        messages.success(request, "Tu usuario fue desactivado.")
        return redirect("login")
    messages.success(request, "Usuario desactivado.")
    return redirect("usuarios:list")


@propietario_required
@require_POST
def reactivar(request, pk):
    try:
        reactivar_usuario(request.user, pk)
    except User.DoesNotExist as error:
        raise Http404 from error
    messages.success(request, "Usuario reactivado.")
    return redirect("usuarios:list")


@propietario_required
@require_POST
def reenviar_invitacion(request, pk):
    try:
        usuario = preparar_reenvio_invitacion(request.user, pk)
    except User.DoesNotExist as error:
        raise Http404 from error
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("usuarios:list")
    if intentar_enviar_invitacion(usuario, request):
        messages.success(request, "Invitación reenviada.")
    else:
        messages.warning(
            request,
            "No pudimos enviar la invitación. Podés intentarlo nuevamente.",
        )
    return redirect("usuarios:list")


@login_required
@never_cache
def mi_cuenta(request):
    form = MiCuentaForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tu perfil fue actualizado.")
        return redirect("usuarios:cuenta")
    return render(
        request,
        "usuarios/cuenta.html",
        {"form": form, "rol": "Propietario" if es_propietario(request.user) else "Usuario"},
    )


class CambiarContrasenaView(LoginRequiredMixin, PasswordChangeView):
    template_name = "shared/model_form.html"
    form_class = CambiarContrasenaForm
    success_url = reverse_lazy("usuarios:cuenta")
    extra_context = {
        "titulo": "Cambiar contraseña",
        "descripcion": "Confirmá tu contraseña actual y elegí una nueva.",
        "texto_boton": "Actualizar contraseña",
        "cancel_url": "usuarios:cuenta",
    }

    def form_valid(self, form):
        messages.success(self.request, "Tu contraseña fue actualizada.")
        return super().form_valid(form)


@method_decorator(never_cache, name="dispatch")
class RecuperarContrasenaView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    form_class = RecuperarContrasenaForm
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    extra_context = {"force_public_layout": True}


@method_decorator(never_cache, name="dispatch")
class RecuperarContrasenaEnviadaView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"
    extra_context = {"force_public_layout": True}


@method_decorator(never_cache, name="dispatch")
class ConfirmarNuevaContrasenaView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    form_class = NuevaContrasenaForm
    success_url = reverse_lazy("password_reset_complete")
    extra_context = {"force_public_layout": True}


@method_decorator(never_cache, name="dispatch")
class ContrasenaActualizadaView(PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"
    extra_context = {"force_public_layout": True}
