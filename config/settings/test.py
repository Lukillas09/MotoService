import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


TEST_DATABASE_URL = (os.getenv("TEST_DATABASE_URL") or "").strip()
if TEST_DATABASE_URL:
    TEST_DATABASE = dj_database_url.parse(
        TEST_DATABASE_URL,
        conn_max_age=0,
    )
    if TEST_DATABASE["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured(
            "TEST_DATABASE_URL must point to a disposable PostgreSQL database."
        )
    DATABASES = {"default": TEST_DATABASE}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
