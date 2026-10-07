from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.motos.models import Moto
from apps.notificaciones.services import obtener_resumen_seguimientos
from apps.servicios.models import Servicio
from apps.usuarios.roles import es_propietario

from .guia import CAPTURAS, TEMAS


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

    return render(
        request,
        "core/search.html",
        {"termino": termino, "clientes": clientes, "motos": motos},
    )
