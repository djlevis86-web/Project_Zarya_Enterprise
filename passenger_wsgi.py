import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_python = os.environ.get(
    "PROJECT_ZARYA_VENV_PYTHON",
    os.path.expanduser("~/venv/bin/python")
)

if os.path.exists(venv_python) and sys.executable != venv_python:
    os.execl(
        venv_python,
        venv_python,
        *sys.argv
    )

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.production"
)

from config.wsgi import application
