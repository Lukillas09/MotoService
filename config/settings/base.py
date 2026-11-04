from pathlib import Path
import os
import re

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be an integer.") from error


def env_positive_int(name, default):
    value = env_int(name, default)
    if value <= 0:
        raise ImproperlyConfigured(f"{name} must be greater than zero.")
    return value


def env_http_header(name, default=""):
    """Nombre de un header HTTP (``CF-Connecting-IP``); vacío significa ninguno."""
    value = (os.getenv(name) or default).strip()
    if value and not re.fullmatch(r"[A-Za-z0-9-]+", value):
        raise ImproperlyConfigured(f"{name} must be an HTTP header name.")
    return value


NIVELES_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def env_log_level(name, default):
    value = (os.getenv(name) or default).strip().upper()
    if value not in NIVELES_LOG:
        raise ImproperlyConfigured(
            f"{name} must be one of {', '.join(NIVELES_LOG)}."
        )
    return value


def construir_logging(nivel):
    """Logging a stdout para Render/Gunicorn.

    Los mensajes nunca deben incluir cuerpos de email, tokens, contraseñas,
    destinatarios ni secretos: sólo identificadores técnicos y clases de error.
    """
    # django.request registra 4xx como WARNING y 5xx como ERROR; nunca se baja
    # de WARNING para no volcar información de cada request.
    if NIVELES_LOG.index(nivel) > NIVELES_LOG.index("WARNING"):
        nivel_minimo_warning = nivel
    else:
        nivel_minimo_warning = "WARNING"
    consola = {"handlers": ["console"], "propagate": False}
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "{asctime} {levelname} {name} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "simple",
            },
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
        "loggers": {
            "django": {**consola, "level": nivel},
            "django.request": {**consola, "level": nivel_minimo_warning},
            "django.security": {**consola, "level": nivel_minimo_warning},
            "apps": {**consola, "level": nivel},
        },
    }


SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
WHATSAPP_DEFAULT_COUNTRY_CODE = os.getenv(
    "WHATSAPP_DEFAULT_COUNTRY_CODE",
    "549",
).strip()
TALLER_NOMBRE = os.getenv("TALLER_NOMBRE", "").strip()

DEFAULT_FROM_EMAIL = (
    os.getenv("DEFAULT_FROM_EMAIL", "MotoService <noreply@localhost>").strip()
    or "MotoService <noreply@localhost>"
)
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "").strip()
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", "").strip()
PASSWORD_RESET_TIMEOUT = env_int("PASSWORD_RESET_TIMEOUT", 86400)
AUTH_LOGIN_IP_MAX_ATTEMPTS = env_positive_int(
    "AUTH_LOGIN_IP_MAX_ATTEMPTS", 20
)
AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS = env_positive_int(
    "AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS", 10
)
AUTH_LOGIN_WINDOW_SECONDS = env_positive_int(
    "AUTH_LOGIN_WINDOW_SECONDS", 900
)
PASSWORD_RESET_IP_MAX_ATTEMPTS = env_positive_int(
    "PASSWORD_RESET_IP_MAX_ATTEMPTS", 10
)
PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS = env_positive_int(
    "PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS", 5
)
PASSWORD_RESET_WINDOW_SECONDS = env_positive_int(
    "PASSWORD_RESET_WINDOW_SECONDS", 3600
)
# Header con la IP real del cliente detrás del proxy; vacío usa REMOTE_ADDR.
AUTH_RATE_LIMIT_CLIENT_IP_HEADER = env_http_header("AUTH_RATE_LIMIT_CLIENT_IP_HEADER")
LISTADO_POR_PAGINA = env_positive_int("LISTADO_POR_PAGINA", 25)

LOG_LEVEL = env_log_level("LOG_LEVEL", "INFO")
LOGGING = construir_logging(LOG_LEVEL)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.clientes",
    "apps.motos",
    "apps.servicios",
    "apps.mantenimientos",
    "apps.notificaciones",
    "apps.exportaciones",
    "apps.usuarios",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.PrivateHtmlNoStoreMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_version",
                "apps.usuarios.context_processors.roles_usuario",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "login"
