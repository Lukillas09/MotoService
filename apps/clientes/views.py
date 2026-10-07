from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.motos.models import Moto

from .forms import ClienteForm
from .models import Cliente


@login_required
def cliente_list(request):
    estado = "archivados" if request.GET.get("estado") == "archivados" else "activos"
    termino = request.GET.get("q", "").strip()
    clientes = (
        Cliente.objects.filter(activo=estado == "activos")
        .buscar(termino)
        .annotate(
            cantidad_motos=Count("motos", filter=Q(motos__activo=True), distinct=True)
        )
    )
    contexto = {
        "clientes": clientes,
        "estado": estado,
        "termino": termino,
    }

    if request.headers.get("HX-Request") == "true":
        return render(request, "clientes/partials/lista.html", contexto)
    return render(request, "clientes/list.html", contexto)


@login_required
def cliente_detail(request, pk):
    clientes = Cliente.objects.prefetch_related(
        Prefetch(
            "motos",
            queryset=Moto.objects.filter(activo=True),
            to_attr="motos_activas",
        )
    )
    cliente = get_object_or_404(clientes, pk=pk)
    return render(request, "clientes/detail.html", {"cliente": cliente})


@login_required
def cliente_create(request):
    form = ClienteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente creado correctamente.")
        return redirect("clientes:detail", pk=cliente.pk)

    return render(
        request,
        "shared/model_form.html",
        {
            "form": form,
            "titulo": "Nuevo cliente",
            "descripcion": "Registrá los datos necesarios para identificarlo y contactarlo.",
            "texto_boton": "Crear cliente",
            "cancel_url": "clientes:list",
        },
    )


@login_required
def cliente_update(request, pk):
    if request.method == "POST":
        with transaction.atomic():
            cliente = get_object_or_404(
                Cliente.objects.select_for_update(no_key=True),
                pk=pk,
            )
            form = ClienteForm(request.POST, instance=cliente)
            if form.is_valid():
                cliente = form.save()
                messages.success(request, "Cliente actualizado correctamente.")
                return redirect("clientes:detail", pk=cliente.pk)
    else:
        cliente = get_object_or_404(Cliente, pk=pk)
        form = ClienteForm(instance=cliente)

    return render(
        request,
        "shared/model_form.html",
        {
            "form": form,
            "titulo": "Editar cliente",
            "descripcion": cliente.nombre_completo,
            "texto_boton": "Guardar cambios",
            "cancel_url": "clientes:detail",
            "cancel_pk": cliente.pk,
        },
    )


@login_required
@require_POST
@transaction.atomic
def cliente_archive(request, pk):
    cliente = get_object_or_404(
        Cliente.objects.select_for_update(no_key=True),
        pk=pk,
        activo=True,
    )
    cliente.activo = False
    cliente.save(update_fields=("activo", "actualizado_en"))
    messages.success(
        request,
        "Cliente archivado. Sus motos conservaron su estado actual.",
    )
    return redirect("clientes:detail", pk=cliente.pk)


@login_required
@require_POST
@transaction.atomic
def cliente_restore(request, pk):
    cliente = get_object_or_404(
        Cliente.objects.select_for_update(no_key=True),
        pk=pk,
        activo=False,
    )
    cliente.activo = True
    cliente.save(update_fields=("activo", "actualizado_en"))
    messages.success(request, "Cliente restaurado.")
    return redirect("clientes:detail", pk=cliente.pk)
