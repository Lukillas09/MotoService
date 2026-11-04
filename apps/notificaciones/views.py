import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.clientes.models import normalizar_telefono_busqueda
from apps.core.paginacion import paginar
from apps.motos.models import normalizar_patente

from .forms import (
    AlertasSeguimientoFiltroForm,
    ContactoForm,
    NoInteresadoForm,
    NotaForm,
    PosponerForm,
    ReabrirForm,
    TurnoForm,
)
from .models import SeguimientoMantenimiento
from .services import (
    AccionSeguimientoInvalida,
    AlertaNoOperativa,
    AlertaObsoleta,
    acordar_turno,
    agregar_nota,
    marcar_contactado,
    marcar_no_interesado,
    obtener_alerta_operativa_actual,
    obtener_resumen_seguimientos,
    posponer_seguimiento,
    reabrir_seguimiento,
    superponer_seguimientos,
)


def _normalizar_busqueda(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").casefold())
    return "".join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    )


def _coincide_busqueda(alerta, termino):
    moto = alerta.moto
    cliente = moto.cliente
    contenido = _normalizar_busqueda(
        " ".join(
            (
                moto.patente or "",
                moto.marca,
                moto.modelo,
                cliente.nombre,
                cliente.apellido,
                cliente.telefono,
                alerta.tipo_mantenimiento.nombre,
            )
        )
    )
    patente = _normalizar_busqueda(moto.patente)
    telefono = normalizar_telefono_busqueda(cliente.telefono).casefold()
    for parte in _normalizar_busqueda(termino).split():
        if parte in contenido:
            continue
        patente_buscada = _normalizar_busqueda(normalizar_patente(parte))
        if patente_buscada and patente_buscada in patente:
            continue
        telefono_buscado = normalizar_telefono_busqueda(parte).casefold()
        if any(caracter.isdigit() for caracter in parte) and telefono_buscado:
            if telefono_buscado in telefono:
                continue
        return False
    return True


def _filtrar_seguimiento(alertas, filtro):
    if filtro == "todos":
        return alertas
    if filtro == "contactados":
        estado = SeguimientoMantenimiento.Estado.CONTACTADO
    elif filtro == "pospuestos":
        estado = SeguimientoMantenimiento.Estado.POSPUESTO
    elif filtro == "turnos":
        estado = SeguimientoMantenimiento.Estado.TURNO_ACORDADO
    elif filtro == "no_interesados":
        estado = SeguimientoMantenimiento.Estado.NO_INTERESADO
    else:
        return [alerta for alerta in alertas if alerta.es_accionable]
    return [
        alerta
        for alerta in alertas
        if alerta.estado_seguimiento == estado
    ]


@login_required
def alerta_list(request):
    resumen = obtener_resumen_seguimientos()
    datos_filtro = request.GET.copy()
    if "seguimiento" not in datos_filtro:
        datos_filtro["seguimiento"] = "accionables"
    filtros = AlertasSeguimientoFiltroForm(
        datos_filtro,
        tipos_mantenimiento=resumen.resumen_tecnico.tipos_configurados,
    )
    alertas = list(resumen.alertas)
    if filtros.is_valid():
        datos = filtros.cleaned_data
        if datos.get("estado"):
            alertas = [
                alerta
                for alerta in alertas
                if alerta.estado.value == datos["estado"]
            ]
        if datos.get("tipo"):
            alertas = [
                alerta
                for alerta in alertas
                if str(alerta.tipo_mantenimiento.pk) == datos["tipo"]
            ]
        if datos.get("q"):
            alertas = [
                alerta
                for alerta in alertas
                if _coincide_busqueda(alerta, datos["q"])
            ]
        alertas = _filtrar_seguimiento(
            alertas,
            datos.get("seguimiento") or "accionables",
        )

    # El cálculo de alertas es en memoria: se pagina la lista ya filtrada y
    # ordenada, mientras los conteos del encabezado siguen usando ``resumen``.
    pagina = paginar(request, alertas)
    contexto = {
        "alertas": pagina.object_list,
        "page_obj": pagina,
        "resumen": resumen,
        "filtros": filtros,
        "hay_filtros": any(
            request.GET.get(campo) for campo in ("q", "estado", "tipo")
        )
        or request.GET.get("seguimiento", "accionables") != "accionables",
    }
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "mantenimientos/partials/lista_alertas.html",
            contexto,
        )
    return render(request, "mantenimientos/alertas.html", contexto)


def _errores_formulario(form):
    return " ".join(
        str(error)
        for errores in form.errors.values()
        for error in errores
    )


def _kwargs_accion(request, moto_pk, tipo_pk, form):
    return {
        "moto_id": moto_pk,
        "tipo_id": tipo_pk,
        "mantenimiento_base_esperado_id": form.cleaned_data[
            "mantenimiento_base"
        ],
        "usuario": request.user,
        "nota": form.cleaned_data.get("nota", ""),
    }


def _manejar_error_accion(request, error):
    if isinstance(error, AlertaObsoleta):
        messages.warning(request, str(error))
    else:
        messages.error(request, str(error))
    return redirect("notificaciones:alertas")


@login_required
@require_POST
def contactar(request, moto_pk, tipo_pk):
    form = ContactoForm(request.POST)
    if not form.is_valid():
        messages.error(request, _errores_formulario(form))
        return redirect("notificaciones:alertas")
    try:
        marcar_contactado(**_kwargs_accion(request, moto_pk, tipo_pk, form))
    except (AlertaNoOperativa, AlertaObsoleta, AccionSeguimientoInvalida) as error:
        return _manejar_error_accion(request, error)
    messages.success(request, "Cliente marcado como contactado.")
    return redirect("notificaciones:alertas")


@login_required
@require_POST
def posponer(request, moto_pk, tipo_pk):
    form = PosponerForm(request.POST)
    if not form.is_valid():
        messages.error(request, _errores_formulario(form))
        return redirect("notificaciones:alertas")
    try:
        posponer_seguimiento(
            **_kwargs_accion(request, moto_pk, tipo_pk, form),
            pospuesto_hasta=form.cleaned_data["pospuesto_hasta"],
        )
    except (AlertaNoOperativa, AlertaObsoleta, AccionSeguimientoInvalida) as error:
        return _manejar_error_accion(request, error)
    fecha = form.cleaned_data["pospuesto_hasta"].strftime("%d/%m/%Y")
    messages.success(request, f"Recordatorio pospuesto hasta {fecha}.")
    return redirect("notificaciones:alertas")


@login_required
@require_POST
def turno(request, moto_pk, tipo_pk):
    form = TurnoForm(request.POST)
    if not form.is_valid():
        messages.error(request, _errores_formulario(form))
        return redirect("notificaciones:alertas")
    try:
        acordar_turno(
            **_kwargs_accion(request, moto_pk, tipo_pk, form),
            turno_para=form.cleaned_data["turno_para"],
        )
    except (AlertaNoOperativa, AlertaObsoleta, AccionSeguimientoInvalida) as error:
        return _manejar_error_accion(request, error)
    messages.success(request, "Turno registrado.")
    return redirect("notificaciones:alertas")


@login_required
@require_POST
def no_interesado(request, moto_pk, tipo_pk):
    form = NoInteresadoForm(request.POST)
    if not form.is_valid():
        messages.error(request, _errores_formulario(form))
        return redirect("notificaciones:alertas")
    try:
        marcar_no_interesado(**_kwargs_accion(request, moto_pk, tipo_pk, form))
    except (AlertaNoOperativa, AlertaObsoleta, AccionSeguimientoInvalida) as error:
        return _manejar_error_accion(request, error)
    messages.success(request, "Cliente marcado como no interesado.")
    return redirect("notificaciones:alertas")


@login_required
@require_POST
def reabrir(request, moto_pk, tipo_pk):
    form = ReabrirForm(request.POST)
    if not form.is_valid():
        messages.error(request, _errores_formulario(form))
        return redirect("notificaciones:alertas")
    try:
        reabrir_seguimiento(**_kwargs_accion(request, moto_pk, tipo_pk, form))
    except (AlertaNoOperativa, AlertaObsoleta, AccionSeguimientoInvalida) as error:
        return _manejar_error_accion(request, error)
    messages.success(request, "Seguimiento reabierto.")
    return redirect("notificaciones:alertas")


@login_required
@require_POST
def nota(request, moto_pk, tipo_pk):
    form = NotaForm(request.POST)
    if not form.is_valid():
        messages.error(request, _errores_formulario(form))
        return redirect("notificaciones:alertas")
    try:
        agregar_nota(**_kwargs_accion(request, moto_pk, tipo_pk, form))
    except (AlertaNoOperativa, AlertaObsoleta, AccionSeguimientoInvalida) as error:
        return _manejar_error_accion(request, error)
    messages.success(request, "Nota agregada al seguimiento.")
    return redirect("notificaciones:alertas")


@login_required
def historial(request, moto_pk, tipo_pk):
    try:
        alerta_tecnica = obtener_alerta_operativa_actual(moto_pk, tipo_pk)
    except AlertaNoOperativa as error:
        messages.warning(request, str(error))
        return redirect("notificaciones:alertas")

    alerta = superponer_seguimientos((alerta_tecnica,))[0]
    eventos = ()
    if alerta.seguimiento is not None:
        eventos = alerta.seguimiento.eventos.select_related("usuario").all()
    return render(
        request,
        "notificaciones/historial.html",
        {"alerta": alerta, "eventos": eventos},
    )
