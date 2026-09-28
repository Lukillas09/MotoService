import re
from urllib.parse import urlparse


ENLACE_RE = re.compile(r"https?://[^/\s]+(?P<path>/accounts/reset/[^\s]+)")


def ruta_desde_email(mensaje):
    coincidencia = ENLACE_RE.search(mensaje.body)
    if coincidencia is None:
        raise AssertionError("El email no contiene un enlace de recuperación.")
    return urlparse(coincidencia.group(0)).path
