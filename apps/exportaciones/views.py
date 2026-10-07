from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from apps.usuarios.roles import propietario_required

from .services import crear_csv, crear_excel_completo
from .utils import nombre_csv, nombre_excel


TIPO_CSV = "text/csv; charset=utf-8"
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _respuesta_descarga(contenido, *, content_type, filename):
    respuesta = HttpResponse(contenido, content_type=content_type)
    respuesta["Content-Disposition"] = f'attachment; filename="{filename}"'
    respuesta["Cache-Control"] = "private, no-store, max-age=0"
    respuesta["Pragma"] = "no-cache"
    return respuesta


def _respuesta_csv(clave):
    return _respuesta_descarga(
        crear_csv(clave),
        content_type=TIPO_CSV,
        filename=nombre_csv(clave),
    )


@propietario_required
@never_cache
def index(request):
    return render(request, "exportaciones/index.html")


@propietario_required
@never_cache
def backup_instructions(request):
    return render(request, "exportaciones/backup.html")


@propietario_required
@never_cache
def clientes_csv(request):
    return _respuesta_csv("clientes")


@propietario_required
@never_cache
def motos_csv(request):
    return _respuesta_csv("motos")


@propietario_required
@never_cache
def servicios_csv(request):
    return _respuesta_csv("servicios")


@propietario_required
@never_cache
def mantenimientos_csv(request):
    return _respuesta_csv("mantenimientos")


@propietario_required
@never_cache
def tipos_mantenimiento_csv(request):
    return _respuesta_csv("tipos-mantenimiento")


@propietario_required
@never_cache
def seguimientos_csv(request):
    return _respuesta_csv("seguimientos")


@propietario_required
@never_cache
def eventos_seguimiento_csv(request):
    return _respuesta_csv("eventos-seguimiento")


@propietario_required
@never_cache
def completo_xlsx(request):
    contenido = crear_excel_completo(request.user)
    return _respuesta_descarga(
        contenido,
        content_type=TIPO_XLSX,
        filename=nombre_excel(),
    )
