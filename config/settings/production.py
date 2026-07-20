import os

from django.core.exceptions import ImproperlyConfigured

from .base import *


DEBUG = False


def _get_production_secret_key():
    value = os.getenv(
        "SECRET_KEY",
        "",
    ).strip()

    if not value:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set in the production environment."
        )

    if value.startswith("django-insecure-"):
        raise ImproperlyConfigured(
            "SECRET_KEY must not use a django-insecure development key."
        )

    if len(value) < 50:
        raise ImproperlyConfigured(
            "SECRET_KEY must contain at least 50 characters."
        )

    if len(set(value)) < 5:
        raise ImproperlyConfigured(
            "SECRET_KEY must contain at least 5 unique characters."
        )

    return value


def _env_non_negative_int(
    name,
    default,
):
    raw_value = os.getenv(
        name,
        "",
    ).strip()

    if not raw_value:
        return default

    try:
        value = int(
            raw_value
        )
    except ValueError as error:
        raise ImproperlyConfigured(
            f"{name} must be an integer."
        ) from error

    if value < 0:
        raise ImproperlyConfigured(
            f"{name} must not be negative."
        )

    return value


SECRET_KEY = _get_production_secret_key()


ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost"
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS"
)

if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.insert(
        1,
        "whitenoise.middleware.WhiteNoiseMiddleware"
    )

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https"
)

SESSION_COOKIE_SECURE = env_bool(
    "SESSION_COOKIE_SECURE",
    True
)

CSRF_COOKIE_SECURE = env_bool(
    "CSRF_COOKIE_SECURE",
    True
)

SECURE_SSL_REDIRECT = env_bool(
    "SECURE_SSL_REDIRECT",
    True
)

SECURE_HSTS_SECONDS = _env_non_negative_int(
    "SECURE_HSTS_SECONDS",
    3600,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False,
)

SECURE_HSTS_PRELOAD = env_bool(
    "SECURE_HSTS_PRELOAD",
    False,
)
