import logging

from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe

from apps.clientes.models import Cliente
from apps.motos.models import Moto
from apps.notificaciones.services import obtener_resumen_seguimientos
from apps.servicios.models import Servicio
from apps.usuarios.roles import es_propietario

from .guia import CAPTURAS, TEMAS
from .pwa import datos_service_worker


logger = logging.getLogger(__name__)


def _temas_guia_visibles(usuario):
    if es_propietario(usuario):
        return TEMAS
    return tuple(tema for tema in TEMAS if tema["slug"] != "exportaciones")


@login_required
def guia_index(request):
    temas = _temas_guia_visibles(request.user)
    return render(
        request,
        "guia/index.html",
        {"temas": temas, "guia_activa": True},
    )


@login_required
def guia_tema(request, slug):
    tema = next((tema for tema in TEMAS if tema["slug"] == slug), None)
    if tema is None:
        raise Http404("Tema no encontrado")
    if slug == "exportaciones" and not es_propietario(request.user):
        raise PermissionDenied

    temas = _temas_guia_visibles(request.user)
    posicion = temas.index(tema)
    capturas = {
        clave: {
            "archivo": f"guide/{archivo}",
            "alt": alt,
            "ancho": 496 if clave == "seguimiento" else 1120,
            "alto": 1000 if clave == "seguimiento" else 872,
            "estrecha": clave == "seguimiento",
        }
        for clave, (archivo, alt) in CAPTURAS.items()
        if finders.find(f"guide/{archivo}")
    }
    return render(
        request,
        "guia/tema.html",
        {
            "tema": tema,
            "contenido": f"guia/temas/{tema['slug']}.html",
            "anterior": temas[posicion - 1] if posicion else None,
            "siguiente": (
                temas[posicion + 1] if posicion + 1 < len(temas) else None
            ),
            "capturas": capturas,
            "guia_activa": True,
        },
    )


@login_required
def dashboard(request):
    resumen_seguimientos = obtener_resumen_seguimientos()
    resumen_alertas = resumen_seguimientos.resumen_tecnico
    cards = [
        {
            "label": "Mantenimientos vencidos",
            "value": len(resumen_alertas.vencidos),
            "tone": "danger",
            "icon": "alert",
            "url": f'{reverse("notificaciones:alertas")}?estado=VENCIDO&seguimiento=todos',
        },
        {
            "label": "Próximos mantenimientos",
            "value": len(resumen_alertas.proximos),
            "tone": "warning",
            "icon": "calendar",
            "url": f'{reverse("notificaciones:alertas")}?estado=PROXIMO&seguimiento=todos',
        },
        {
            "label": "Clientes",
            "value": Cliente.objects.filter(activo=True).count(),
            "tone": "primary",
            "icon": "users",
            "url": reverse("clientes:list"),
        },
        {
            "label": "Motos",
            "value": Moto.objects.filter(activo=True).count(),
            "tone": "purple",
            "icon": "moto-solid",
            "url": reverse("motos:list"),
        },
    ]
    ultimos_servicios = Servicio.objects.con_detalle()[:5]
    return render(
        request,
        "core/dashboard.html",
        {
            "cards": cards,
            "resumen_alertas": resumen_alertas,
            "resumen_seguimientos": resumen_seguimientos,
            "alertas_prioritarias": resumen_seguimientos.accionables[:5],
            "ultimos_servicios": ultimos_servicios,
        },
    )


@login_required
def busqueda_global(request):
    termino = request.GET.get("q", "").strip()
    clientes = Cliente.objects.none()
    motos = Moto.objects.none()
    servicios = Servicio.objects.none()

    if termino:
        clientes = (
            Cliente.objects.filter(activo=True)
            .buscar(termino)
            .annotate(
                cantidad_motos=Count(
                    "motos", filter=Q(motos__activo=True), distinct=True
                )
            )[:8]
        )
        motos = (
            Moto.objects.filter(activo=True)
            .select_related("cliente")
            .buscar(termino)[:8]
        )
        # Todos los estados: un servicio cancelado también es historial útil.
        servicios = Servicio.objects.con_detalle().buscar(termino)[:8]

    return render(
        request,
        "core/search.html",
        {
            "termino": termino,
            "clientes": clientes,
            "motos": motos,
            "servicios": servicios,
        },
    )


@login_not_required
@csrf_exempt
@require_safe
@cache_control(no_store=True)
def healthz(request):
    """Healthcheck público para Render y el ping externo: no usa sesión ni datos."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as error:
        logger.warning(
            "Healthcheck sin base de datos. error_type=%s", type(error).__name__
        )
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


@login_not_required
@require_safe
def service_worker(request):
    """Service worker en la raíz para que su alcance sea todo el sitio.

    Se renderiza sin request: no usa sesión ni context processors.
    """
    contenido = render_to_string("pwa/service-worker.js", datos_service_worker())
    response = HttpResponse(
        contenido, content_type="application/javascript; charset=utf-8"
    )
    # El navegador revalida en cada carga y detecta un deploy nuevo enseguida.
    response["Cache-Control"] = "no-cache"
    return response


@login_not_required
@require_safe
def offline(request):
    """Página pública que el service worker muestra cuando no hay red."""
    response = HttpResponse(render_to_string("offline.html"))
    response["Cache-Control"] = "no-cache"
    return response
