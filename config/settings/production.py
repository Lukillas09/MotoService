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
# Si Supabase está pausado o no responde, /healthz/ devuelve 503 en segundos en
# lugar de colgar al worker. Puede ajustarse con ?connect_timeout= en la URL.
DATABASES["default"].setdefault("OPTIONS", {}).setdefault("connect_timeout", 10)

# Railway hace el healthcheck de deploy con este Host, por HTTP y sin pasar
# por su proxy; el edge público no enruta ese Host hacia el servicio.
RAILWAY_HEALTHCHECK_HOST = "healthcheck.railway.app"
ALLOWED_HOSTS = [  # noqa: F405
    *env_list("ALLOWED_HOSTS"),  # noqa: F405
    RAILWAY_HEALTHCHECK_HOST,
]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
AUTH_RATE_LIMIT_CLIENT_IP_META_KEY = "HTTP_X_REAL_IP"
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
