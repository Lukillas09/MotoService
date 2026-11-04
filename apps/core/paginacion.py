from django.conf import settings
from django.core.paginator import Paginator


def paginar(request, elementos):
    """Devuelve la página pedida en ``?page=`` de un QuerySet ordenado o una lista.

    ``get_page`` convierte un número inválido en la primera página y uno fuera
    de rango en la última, así un enlace viejo nunca produce un error 500.
    """
    paginador = Paginator(elementos, settings.LISTADO_POR_PAGINA)
    return paginador.get_page(request.GET.get("page"))
