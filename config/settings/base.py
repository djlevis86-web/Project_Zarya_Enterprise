from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
import os


BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name, default=""):
    value = os.getenv(name, default)

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def env_path(name, default):
    value = os.getenv(name, "").strip()

    if not value:
        return default

    return Path(value)


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-local-dev-key-change-me"
)

DEBUG = env_bool(
    "DEBUG",
    False
)

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS"
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS"
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'users',
    'invoices',
    'reports',
    'ocr',
    'system',
    'audit.apps.AuditConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND':
            'django.template.backends.django.DjangoTemplates',

        'DIRS': [
            BASE_DIR / 'templates'
        ],

        'APP_DIRS': True,

        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'config.context_processors.project_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    "users.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static'
]

STATIC_ROOT = env_path(
    "STATIC_ROOT",
    BASE_DIR / "staticfiles"
)

MEDIA_URL = '/media/'

MEDIA_ROOT = env_path(
    "MEDIA_ROOT",
    BASE_DIR / 'media'
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv(
            "DATABASE_URL",
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
        )
    )
}

LOGIN_URL = '/'

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    ""
)

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "redis://127.0.0.1:6379/0"
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://127.0.0.1:6379/0"
)

CELERY_ACCEPT_CONTENT = [
    "json",
]

CELERY_TASK_SERIALIZER = "json"

CELERY_RESULT_SERIALIZER = "json"

CELERY_TIMEZONE = "UTC"
