"""Configuración de Gunicorn para Render (``gunicorn -c gunicorn.conf.py``).

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
# Render enruta al puerto de PORT (10000 por defecto).
bind = f"0.0.0.0:{os.getenv('PORT') or '10000'}"
# El plan free tiene 512 MB: 2 workers sync entran con margen.
workers = _entero_positivo("WEB_CONCURRENCY", 2)
timeout = _entero_positivo("GUNICORN_TIMEOUT", 60)
graceful_timeout = _entero_positivo("GUNICORN_GRACEFUL_TIMEOUT", 30)

# Access log a stdout y errores a stderr: Render conserva ambos.
accesslog = "-"
errorlog = "-"
loglevel = (os.getenv("LOG_LEVEL") or "info").strip().lower()
# Sin IP, referer, user agent ni query string: las búsquedas llevan nombres,
# teléfonos y patentes.
access_log_format = '%(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(M)sms'

RUTA_CON_TOKEN = re.compile(r"^/accounts/reset/[^/]+/[^/]+/")
RUTA_HEALTHCHECK = "/healthz/"


class AccessLogSinDatosSensibles(Logger):
    """Oculta tokens de invitación/recuperación y omite healthchecks exitosos."""

    def access(self, resp, req, environ, request_time):
        # Render lo consulta cada pocos segundos y el ping externo cada 10
        # minutos; sólo interesa cuando falla.
        exitoso = getattr(resp, "status_code", 500) < 400
        if environ.get("PATH_INFO") == RUTA_HEALTHCHECK and exitoso:
            return
        super().access(resp, req, environ, request_time)

    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        ruta = atoms.get("U") or ""
        atoms["U"] = RUTA_CON_TOKEN.sub("/accounts/reset/<oculto>/", ruta)
        return atoms


logger_class = AccessLogSinDatosSensibles
