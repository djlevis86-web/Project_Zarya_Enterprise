from .base import *


DEBUG = False

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
    False
)

CSRF_COOKIE_SECURE = env_bool(
    "CSRF_COOKIE_SECURE",
    False
)

SECURE_SSL_REDIRECT = env_bool(
    "SECURE_SSL_REDIRECT",
    False
)
