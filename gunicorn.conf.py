"""Configuración de Gunicorn para Railway (``gunicorn --config gunicorn.conf.py``).

Workers y timeouts se ajustan con variables de entorno, sin tocar código.
"""

import os
import re

from gunicorn.glogging import Logger


def _entero_positivo(nombre, default):
    valor = int(os.getenv(nombre) or default)
    if valor <= 0:
        raise ValueError(f"{nombre} must be greater than zero.")
    return valor


wsgi_app = "config.wsgi:application"
bind = f"0.0.0.0:{os.getenv('PORT') or '8000'}"
workers = _entero_positivo("GUNICORN_WORKERS", 2)
timeout = _entero_positivo("GUNICORN_TIMEOUT", 60)
graceful_timeout = _entero_positivo("GUNICORN_GRACEFUL_TIMEOUT", 30)

# Access log a stdout y errores a stderr: Railway conserva ambos.
accesslog = "-"
errorlog = "-"
loglevel = (os.getenv("LOG_LEVEL") or "info").strip().lower()
# Sin IP, referer, user agent ni query string: las búsquedas llevan nombres,
# teléfonos y patentes.
access_log_format = '%(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(M)sms'

RUTA_CON_TOKEN = re.compile(r"^/accounts/reset/[^/]+/[^/]+/")


class AccessLogSinDatosSensibles(Logger):
    """Oculta el UID y el token de los enlaces de invitación y recuperación."""

    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        ruta = atoms.get("U") or ""
        atoms["U"] = RUTA_CON_TOKEN.sub("/accounts/reset/<oculto>/", ruta)
        return atoms


logger_class = AccessLogSinDatosSensibles
