from .base import *  # noqa: F403


# Prefer a Django-specific flag; some launchers set DEBUG to non-boolean values.
DEBUG = env_bool("DJANGO_DEBUG", env_bool("DEBUG", True))  # noqa: F405
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ALLOWED_HOSTS = list(  # noqa: F405
    dict.fromkeys(
        [
            *env_list("ALLOWED_HOSTS"),  # noqa: F405
            "localhost",
            "127.0.0.1",
        ]
    )
)

# Development can run with DATABASE_URL against PostgreSQL. If DATABASE_URL is
# empty, SQLite is used only as a local fallback to keep first setup simple.
