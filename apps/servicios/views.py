from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.core.paginacion import paginar
from apps.motos.models import Moto

from .forms import ServicioFiltroForm, ServicioForm
from .models import Servicio
from .services import guardar_servicio_y_mantenimientos


def _moto_inicial(moto_id):
    if not moto_id:
        return None
    try:
        moto_id = int(moto_id)
    except (TypeError, ValueError) as error:
        raise Http404("Moto inexistente.") from error
    return get_object_or_404(
        Moto.objects.select_related("cliente"),
        pk=moto_id,
        activo=True,
        cliente__activo=True,
    )


def _agregar_error_de_dominio(form, error):
    if hasattr(error, "message_dict"):
        for campo, mensajes_error in error.message_dict.items():
            destino = campo if campo in form.fields else None
            for mensaje in mensajes_error:
                form.add_error(destino, mensaje)
    else:
        for mensaje in error.messages:
            form.add_error(None, mensaje)


@login_required
def servicio_list(request):
    formulario_filtros = ServicioFiltroForm(request.GET or None)
    servicios = Servicio.objects.con_detalle()

    if formulario_filtros.is_valid():
        datos = formulario_filtros.cleaned_data
        servicios = servicios.buscar(datos.get("q"))
        if datos.get("estado"):
            servicios = servicios.filter(estado=datos["estado"])
        if datos.get("desde"):
            servicios = servicios.filter(fecha__gte=datos["desde"])
        if datos.get("hasta"):
            servicios = servicios.filter(fecha__lte=datos["hasta"])

    pagina = paginar(request, servicios)
    contexto = {
        "servicios": pagina.object_list,
        "page_obj": pagina,
        "filtros": formulario_filtros,
        "hay_filtros": any(
            request.GET.get(campo) for campo in ("q", "estado", "desde", "hasta")
        ),
    }
    if request.headers.get("HX-Request") == "true":
        return render(request, "servicios/partials/lista.html", contexto)
    return render(request, "servicios/list.html", contexto)


@login_required
def servicio_detail(request, pk):
    servicio = get_object_or_404(Servicio.objects.con_detalle(), pk=pk)
    return render(request, "servicios/detail.html", {"servicio": servicio})


@login_required
def servicio_create(request):
    moto_inicial = _moto_inicial(request.GET.get("moto"))
    form = ServicioForm(
        request.POST or None,
        initial={"moto": moto_inicial} if moto_inicial else None,
    )
    if request.method == "POST" and form.is_valid():
        servicio = form.save(commit=False)
        try:
            guardar_servicio_y_mantenimientos(
                servicio,
                form.cleaned_data["mantenimientos"],
                creado_por=request.user,
            )
        except ValidationError as error:
            _agregar_error_de_dominio(form, error)
        else:
            messages.success(request, "Servicio registrado correctamente.")
            return redirect("servicios:detail", pk=servicio.pk)

    moto_contexto = None
    if form.is_bound and form.data.get("moto"):
        try:
            moto_contexto = Moto.objects.select_related("cliente").get(
                pk=form.data.get("moto"),
                activo=True,
                cliente__activo=True,
            )
        except (Moto.DoesNotExist, TypeError, ValueError):
            pass
    elif moto_inicial:
        moto_contexto = moto_inicial

    return render(
        request,
        "servicios/form.html",
        {
            "form": form,
            "titulo": "Nuevo servicio",
            "texto_boton": "Registrar servicio",
            "moto_contexto": moto_contexto,
        },
    )


@login_required
def servicio_update(request, pk):
    servicio = get_object_or_404(Servicio.objects.con_detalle(), pk=pk)
    form = ServicioForm(request.POST or None, instance=servicio)
    if request.method == "POST" and form.is_valid():
        servicio = form.save(commit=False)
        try:
            guardar_servicio_y_mantenimientos(
                servicio,
                form.cleaned_data["mantenimientos"],
            )
        except ValidationError as error:
            _agregar_error_de_dominio(form, error)
        else:
            messages.success(request, "Servicio actualizado correctamente.")
            return redirect("servicios:detail", pk=servicio.pk)

    return render(
        request,
        "servicios/form.html",
        {
            "form": form,
            "servicio": servicio,
            "titulo": "Editar servicio",
            "texto_boton": "Guardar cambios",
            "moto_contexto": servicio.moto,
        },
    )


@login_required
@require_POST
def servicio_cancel(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    if servicio.estado == Servicio.Estado.CANCELADO:
        messages.info(request, "El servicio ya estaba cancelado.")
    else:
        servicio.estado = Servicio.Estado.CANCELADO
        servicio.save(update_fields=("estado", "actualizado_en"))
        messages.success(request, "Servicio cancelado. El registro se conservó en el historial.")
    return redirect("servicios:detail", pk=servicio.pk)


@login_required
@require_GET
def moto_context(request):
    moto_id = request.GET.get("moto")
    if not moto_id:
        return HttpResponse("")
    try:
        moto_id = int(moto_id)
    except (TypeError, ValueError) as error:
        raise Http404("Moto inexistente.") from error
    moto = get_object_or_404(
        Moto.objects.select_related("cliente"),
        pk=moto_id,
        activo=True,
        cliente__activo=True,
    )
    return render(request, "servicios/partials/moto_contexto.html", {"moto": moto})
