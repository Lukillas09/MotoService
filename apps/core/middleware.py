from urllib.parse import urlsplit

from django.conf import settings
from django.utils.cache import patch_cache_control


class PrivateHtmlNoStoreMiddleware:
    """Evita que el navegador conserve páginas privadas autenticadas."""

    def __init__(self, get_response):
        self.get_response = get_response
        static_path = urlsplit(settings.STATIC_URL).path
        self.static_prefix = f"/{static_path.lstrip('/')}"
        if not self.static_prefix.endswith("/"):
            self.static_prefix = f"{self.static_prefix}/"

    def __call__(self, request):
        response = self.get_response(request)
        if self._debe_evitar_cache(request, response):
            patch_cache_control(response, private=True, no_store=True)
            if "Pragma" not in response:
                response["Pragma"] = "no-cache"
            if "Expires" not in response:
                response["Expires"] = "0"
        return response

    def _debe_evitar_cache(self, request, response):
        # El tipo se revisa antes que el usuario: así las respuestas que no son
        # HTML (como /healthz/) no cargan la sesión ni consultan la base.
        content_type = response.headers.get("Content-Type", "")
        media_type = content_type.partition(";")[0].strip().lower()
        if media_type != "text/html":
            return False

        usuario = getattr(request, "user", None)
        if not usuario or not usuario.is_authenticated:
            return False

        ruta = request.path_info
        if ruta == self.static_prefix.removesuffix("/") or ruta.startswith(
            self.static_prefix
        ):
            return False

        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match and resolver_match.url_name in {"login", "service-worker", "offline"}:
            return False

        content_disposition = response.headers.get("Content-Disposition", "")
        cache_control = response.headers.get("Cache-Control", "")
        if (
            "attachment" in content_disposition.lower()
            and "no-store" in cache_control.lower()
        ):
            return False

        return True
