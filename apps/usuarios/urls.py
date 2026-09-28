from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("cuenta/", views.mi_cuenta, name="cuenta"),
    path(
        "cuenta/cambiar-contrasena/",
        views.CambiarContrasenaView.as_view(),
        name="cambiar_contrasena",
    ),
    path("usuarios/", views.lista_usuarios, name="list"),
    path("usuarios/nuevo/", views.crear_usuario, name="create"),
    path("usuarios/<int:pk>/editar/", views.editar_usuario, name="update"),
    path(
        "usuarios/<int:pk>/desactivar/",
        views.desactivar,
        name="deactivate",
    ),
    path(
        "usuarios/<int:pk>/reactivar/",
        views.reactivar,
        name="reactivate",
    ),
    path(
        "usuarios/<int:pk>/reenviar-invitacion/",
        views.reenviar_invitacion,
        name="resend_invitation",
    ),
]

