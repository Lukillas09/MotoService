from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def url_pagina(context, numero):
    """Arma la URL de otra página conservando búsqueda y filtros actuales."""
    request = context["request"]
    parametros = request.GET.copy()
    parametros.pop("page", None)
    if int(numero) > 1:
        parametros["page"] = numero
    consulta = parametros.urlencode()
    return f"{request.path}?{consulta}" if consulta else request.path


@register.simple_tag
def paginas_visibles(page_obj):
    return page_obj.paginator.get_elided_page_range(
        page_obj.number,
        on_each_side=1,
        on_ends=1,
    )
