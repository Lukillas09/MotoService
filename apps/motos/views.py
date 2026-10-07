from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.clientes.models import Cliente
from apps.mantenimientos.services import obtener_estados_moto
from apps.notificaciones.services import superponer_estados_moto
from apps.servicios.models import Servicio

from .forms import MotoForm
from .models import Moto


def _cliente_id_enviado(request):
    try:
        return int(request.POST.get("cliente", ""))
    except (TypeError, ValueError):
        return None


@login_required
def moto_list(request):
    estado = "archivadas" if request.GET.get("estado") == "archivadas" else "activas"
    termino = request.GET.get("q", "").strip()
    motos = (
        Moto.objects.filter(activo=estado == "activas")
        .select_related("cliente")
        .buscar(termino)
    )
    contexto = {"motos": motos, "estado": estado, "termino": termino}

    if request.headers.get("HX-Request") == "true":
        return render(request, "motos/partials/lista.html", contexto)
    return render(request, "motos/list.html", contexto)


@login_required
def moto_detail(request, pk):
    motos = Moto.objects.select_related("cliente").prefetch_related(
        Prefetch(
            "servicios",
            queryset=Servicio.objects.con_detalle(),
            to_attr="historial_servicios",
        )
    )
    moto = get_object_or_404(motos, pk=pk)
    estados_mantenimiento = superponer_estados_moto(
        obtener_estados_moto(moto)
    )
    whatsapp_url = next(
        (
            item.alerta_seguimiento.whatsapp_url
            for item in estados_mantenimiento
            if item.alerta_seguimiento and item.alerta_seguimiento.whatsapp_url
        ),
        None,
    )
    return render(
        request,
        "motos/detail.html",
        {
            "moto": moto,
            "estados_mantenimiento": estados_mantenimiento,
            "whatsapp_url": whatsapp_url,
        },
    )


@login_required
def moto_create(request):
    cliente_inicial = None
    cliente_id = request.GET.get("cliente")
    if cliente_id:
        try:
            cliente_id = int(cliente_id)
        except (TypeError, ValueError) as error:
            raise Http404("Cliente inexistente.") from error
        cliente_inicial = get_object_or_404(Cliente, pk=cliente_id, activo=True)

    form = MotoForm(
        request.POST or None,
        initial={"cliente": cliente_inicial} if cliente_inicial else None,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            try:
                cliente = Cliente.objects.select_for_update(no_key=True).get(
                    pk=form.cleaned_data["cliente"].pk
                )
            except Cliente.DoesNotExist:
                form.add_error("cliente", "El cliente seleccionado ya no existe.")
            else:
                if not cliente.activo:
                    form.add_error(
                        "cliente",
                        "Restaurá el cliente antes de registrar una moto nueva.",
                    )
                else:
                    moto = form.save(commit=False)
                    moto.cliente = cliente
                    moto.save()
                    messages.success(request, "Moto creada correctamente.")
                    return redirect("motos:detail", pk=moto.pk)

    return render(
        request,
        "shared/model_form.html",
        {
            "form": form,
            "titulo": "Nueva moto",
            "descripcion": "Registrá los datos conocidos. La patente puede quedar vacía.",
            "texto_boton": "Crear moto",
            "cancel_url": "clientes:detail" if cliente_inicial else "motos:list",
            "cancel_pk": cliente_inicial.pk if cliente_inicial else None,
        },
    )


@login_required
def moto_update(request, pk):
    motos = Moto.objects.select_related("cliente")
    if request.method == "POST":
        with transaction.atomic():
            cliente_id = _cliente_id_enviado(request)
            if cliente_id is not None:
                # El formulario sigue validando la selección. Este lock solo
                # estabiliza el estado del propietario antes de bloquear Moto.
                Cliente.objects.select_for_update(no_key=True).filter(
                    pk=cliente_id
                ).first()
            moto = get_object_or_404(
                Moto.objects.select_for_update(no_key=True),
                pk=pk,
            )
            form = MotoForm(request.POST, instance=moto)
            if form.is_valid():
                moto = form.save()
                messages.success(request, "Moto actualizada correctamente.")
                return redirect("motos:detail", pk=moto.pk)
    else:
        moto = get_object_or_404(motos, pk=pk)
        form = MotoForm(instance=moto)

    return render(
        request,
        "shared/model_form.html",
        {
            "form": form,
            "titulo": "Editar moto",
            "descripcion": str(moto),
            "texto_boton": "Guardar cambios",
            "cancel_url": "motos:detail",
            "cancel_pk": moto.pk,
        },
    )


@login_required
@require_POST
@transaction.atomic
def moto_archive(request, pk):
    moto = get_object_or_404(
        Moto.objects.select_for_update(no_key=True),
        pk=pk,
        activo=True,
    )
    moto.activo = False
    moto.save(update_fields=("activo", "actualizado_en"))
    messages.success(request, "Moto archivada.")
    return redirect("motos:detail", pk=moto.pk)


@login_required
@require_POST
@transaction.atomic
def moto_restore(request, pk):
    moto = get_object_or_404(
        Moto.objects.select_for_update(no_key=True),
        pk=pk,
        activo=False,
    )
    moto.activo = True
    moto.save(update_fields=("activo", "actualizado_en"))
    messages.success(request, "Moto restaurada.")
    return redirect("motos:detail", pk=moto.pk)
