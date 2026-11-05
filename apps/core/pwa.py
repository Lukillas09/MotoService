import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.templatetags.static import static
from django.urls import reverse

from config.version import APP_VERSION


# Recursos públicos que el service worker precarga. Sólo estáticos propios:
# nunca HTML autenticado ni respuestas con datos del taller.
RECURSOS_PRECARGADOS = (
    "css/app.css",
    "js/app.js",
    "js/guide.js",
    "manifest.webmanifest",
    "icons/ui.svg",
    "icons/motoservice-mark-96.png",
    "icons/favicon-32.png",
    "images/moto-generic.png",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "icons/icon-maskable-192.png",
    "icons/icon-maskable-512.png",
    "icons/apple-touch-icon.png",
)
TEMPLATES_OFFLINE = ("offline.html", "error_base.html")

_datos_en_produccion = None


def prefijo_estaticos():
    ruta = urlsplit(settings.STATIC_URL).path
    return f"/{ruta.strip('/')}/"


def _calcular_datos():
    # static() es lo mismo que {% static %}: con el storage de manifiesto
    # devuelve las URLs con hash que piden los templates.
    urls = [static(ruta) for ruta in RECURSOS_PRECARGADOS]
    huella = hashlib.sha256()
    for ruta, url in zip(RECURSOS_PRECARGADOS, urls):
        huella.update(url.encode())
        archivo = finders.find(ruta)
        if archivo:
            huella.update(Path(archivo).read_bytes())
    for nombre in TEMPLATES_OFFLINE:
        huella.update(get_template(nombre).template.source.encode())
    return {
        "nombre_cache": f"motoservice-{APP_VERSION}-{huella.hexdigest()[:12]}",
        "recursos_json": json.dumps(urls),
        "offline_url": reverse("core:offline"),
        "prefijo_estaticos": prefijo_estaticos(),
    }


def datos_service_worker():
    """Lista de precarga y nombre de caché; cambian sólo cuando cambia un asset.

    En producción los archivos no cambian entre deploys, así que se calcula una
    vez por proceso. En desarrollo se recalcula para reflejar cada edición.
    """
    global _datos_en_produccion
    if settings.DEBUG:
        return _calcular_datos()
    if _datos_en_produccion is None:
        _datos_en_produccion = _calcular_datos()
    return _datos_en_produccion
