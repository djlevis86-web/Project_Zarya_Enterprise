from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost'
]


AUTHENTICATION_BACKENDS = [
    "users.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]
