from .base import *  # noqa: F403


DEBUG = False
EMAIL_BACKEND = "apps.core.email_backends.BrevoEmailBackend"

MIDDLEWARE = [  # noqa: F405
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],  # noqa: F405
]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECRET_KEY = (os.getenv("SECRET_KEY") or "").strip()  # noqa: F405
if not SECRET_KEY or SECRET_KEY == "change-me":
    raise RuntimeError(
        "SECRET_KEY must be set in production and cannot use the placeholder value."
    )

DATABASE_URL = os.getenv("DATABASE_URL", "")  # noqa: F405
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in production.")

if not BREVO_API_KEY:  # noqa: F405
    raise RuntimeError("BREVO_API_KEY must be set in production.")

if not BREVO_FROM_EMAIL:  # noqa: F405
    raise RuntimeError("BREVO_FROM_EMAIL must be set in production.")

if not BREVO_FROM_NAME:  # noqa: F405
    raise RuntimeError("BREVO_FROM_NAME must be set in production.")

DATABASES = {  # noqa: F405
    "default": dj_database_url.parse(  # noqa: F405
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )
}
# Si Supabase está pausado o no responde, migrate y /healthz/ fallan en segundos
# en lugar de colgar al worker. Puede ajustarse con ?connect_timeout= en la URL.
DATABASES["default"].setdefault("OPTIONS", {}).setdefault("connect_timeout", 10)

# El pooler de Supabase en modo Transaction (6543) no conserva la sesión entre
# sentencias: rompe LOCK TABLE y select_for_update. Se exige el modo Session.
if DATABASES["default"].get("HOST", "").endswith(".pooler.supabase.com") and str(
    DATABASES["default"].get("PORT")
) == "6543":
    raise RuntimeError(
        "DATABASE_URL must use the Supabase Session pooler (port 5432), "
        "not the Transaction pooler (port 6543)."
    )

# Render hace los health checks con el subdominio onrender.com como Host y lo
# expone en RENDER_EXTERNAL_HOSTNAME; se agrega para no cancelar el deploy si
# falta en ALLOWED_HOSTS.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")  # noqa: F405
RENDER_EXTERNAL_HOSTNAME = (os.getenv("RENDER_EXTERNAL_HOSTNAME") or "").strip()  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Render pone Cloudflare delante de los web services: CF-Connecting-IP lo
# sobrescribe Cloudflare, mientras que X-Forwarded-For conserva lo que mande
# el cliente. Ver docs/architecture.md.
AUTH_RATE_LIMIT_CLIENT_IP_HEADER = env_http_header(  # noqa: F405
    "AUTH_RATE_LIMIT_CLIENT_IP_HEADER", "CF-Connecting-IP"
)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
