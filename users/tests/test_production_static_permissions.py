from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase

from config.storage import (
    ZaryaCompressedManifestStaticFilesStorage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_ENVIRONMENT_VARIABLES = (
    "SECRET_KEY",
    "SESSION_COOKIE_SECURE",
    "CSRF_COOKIE_SECURE",
    "SECURE_SSL_REDIRECT",
    "SECURE_HSTS_SECONDS",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
)

VALID_SECRET_KEY = (
    "zarya-production-secret-"
    "A7!kQ9#mR4@vL8$xT2&pN6-Z8@q"
)


class ProductionStaticPermissionsTests(
    SimpleTestCase
):
    def _run_production_settings(
        self,
        output_expression,
    ):
        process_environment = os.environ.copy()

        for variable_name in (
            PRODUCTION_ENVIRONMENT_VARIABLES
        ):
            process_environment.pop(
                variable_name,
                None,
            )

        process_environment[
            "SECRET_KEY"
        ] = VALID_SECRET_KEY

        code = f"""
import json
from unittest.mock import patch

with patch(
    "dotenv.load_dotenv",
    return_value=False,
):
    from config.settings import production as settings

print({output_expression})
"""

        return subprocess.run(
            [
                sys.executable,
                "-c",
                code,
            ],
            cwd=PROJECT_ROOT,
            env=process_environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_static_storage_owns_nginx_safe_permissions(
        self,
    ):
        storage = (
            ZaryaCompressedManifestStaticFilesStorage()
        )

        self.assertEqual(
            storage.file_permissions_mode,
            0o644,
        )
        self.assertEqual(
            storage.directory_permissions_mode,
            0o755,
        )

    def test_permissions_cannot_fall_back_to_process_umask(
        self,
    ):
        storage = (
            ZaryaCompressedManifestStaticFilesStorage(
                file_permissions_mode=0o600,
                directory_permissions_mode=0o700,
            )
        )

        self.assertEqual(
            storage.file_permissions_mode,
            0o644,
        )
        self.assertEqual(
            storage.directory_permissions_mode,
            0o755,
        )

    def test_production_uses_project_static_storage_only(
        self,
    ):
        output_expression = """json.dumps({
    "default": settings.STORAGES["default"]["BACKEND"],
    "staticfiles": settings.STORAGES["staticfiles"]["BACKEND"],
})"""

        result = self._run_production_settings(
            output_expression,
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )

        storage_backends = json.loads(
            result.stdout.strip()
        )

        self.assertEqual(
            storage_backends["default"],
            "django.core.files.storage.FileSystemStorage",
        )
        self.assertEqual(
            storage_backends["staticfiles"],
            (
                "config.storage."
                "ZaryaCompressedManifestStaticFilesStorage"
            ),
        )
