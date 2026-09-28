from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)

from apps.core.forms import BootstrapFormMixin

from .roles import ROL_PROPIETARIO, ROL_USUARIO, rol_de_usuario
from .services import normalizar_email, validar_email_unico


User = get_user_model()


class EmailUnicoMixin:
    def clean_email(self):
        email = normalizar_email(self.cleaned_data.get("email"))
        if not email:
            raise forms.ValidationError("Ingresá un correo electrónico.")
        excluir_pk = self.instance.pk if getattr(self.instance, "pk", None) else None
        validar_email_unico(email, excluir_pk=excluir_pk)
        return email


class UsuarioBaseForm(EmailUnicoMixin, BootstrapFormMixin, forms.ModelForm):
    ROL_CHOICES = (
        (ROL_USUARIO, "Usuario"),
        (ROL_PROPIETARIO, "Propietario"),
    )
    rol = forms.ChoiceField(
        label="Rol",
        choices=ROL_CHOICES,
        help_text="Propietario administra cuentas; Usuario usa las funciones del taller.",
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "username": "Nombre de usuario",
            "email": "Correo electrónico",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        help_texts = {
            "username": "Se utilizará junto con la contraseña para ingresar.",
        }

    def clean_username(self):
        return self.cleaned_data["username"].strip()


class UsuarioCreateForm(UsuarioBaseForm):
    field_order = ("first_name", "last_name", "username", "email", "rol")


class UsuarioUpdateForm(UsuarioBaseForm):
    contrasena_actual = forms.CharField(
        label="Contraseña actual",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Necesaria solamente si cambiás tu propio correo.",
    )
    field_order = (
        "first_name",
        "last_name",
        "username",
        "email",
        "rol",
        "contrasena_actual",
    )

    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        self.fields["rol"].initial = rol_de_usuario(self.instance)
        if self.instance.is_superuser:
            self.fields["rol"].initial = ROL_PROPIETARIO
            self.fields["rol"].disabled = True
            self.fields["rol"].help_text = (
                "Los superusuarios siempre son Propietarios en MotoService."
            )
        if actor is None or actor.pk != self.instance.pk:
            self.fields.pop("contrasena_actual")

    def clean(self):
        cleaned_data = super().clean()
        if self.actor and self.actor.pk == self.instance.pk:
            nuevo_email = normalizar_email(cleaned_data.get("email"))
            if nuevo_email != normalizar_email(self.instance.email):
                password = cleaned_data.get("contrasena_actual")
                if not password or not self.actor.check_password(password):
                    self.add_error(
                        "contrasena_actual",
                        "Ingresá tu contraseña actual para cambiar el correo.",
                    )
        return cleaned_data


class MiCuentaForm(EmailUnicoMixin, BootstrapFormMixin, forms.ModelForm):
    contrasena_actual = forms.CharField(
        label="Contraseña actual",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="La pediremos únicamente si cambiás tu correo.",
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        nuevo_email = normalizar_email(cleaned_data.get("email"))
        if nuevo_email != normalizar_email(self.instance.email):
            password = cleaned_data.get("contrasena_actual")
            if not password or not self.instance.check_password(password):
                self.add_error(
                    "contrasena_actual",
                    "Ingresá tu contraseña actual para cambiar el correo.",
                )
        return cleaned_data


class RecuperarContrasenaForm(BootstrapFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Correo electrónico"
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "placeholder": "nombre@correo.com"}
        )

    def get_users(self, email):
        usuarios = list(super().get_users(normalizar_email(email)))
        if len(usuarios) == 1:
            yield usuarios[0]


class NuevaContrasenaForm(BootstrapFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar contraseña"


class CambiarContrasenaForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
