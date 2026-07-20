import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SECURITY_ENVIRONMENT_VARIABLES = (
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


class ProductionSecuritySettingsTests(SimpleTestCase):

    def _run_production_settings(
        self,
        *,
        environment=None,
        output_expression="'IMPORTED'",
    ):
        process_environment = os.environ.copy()

        for variable_name in SECURITY_ENVIRONMENT_VARIABLES:
            process_environment.pop(
                variable_name,
                None,
            )

        if environment:
            process_environment.update(
                environment
            )

        code = f"""
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

    def assert_secret_key_rejected(
        self,
        environment,
    ):
        result = self._run_production_settings(
            environment=environment,
        )

        self.assertNotEqual(
            result.returncode,
            0,
            result.stdout,
        )
        self.assertIn(
            "SECRET_KEY",
            result.stderr,
        )

    def test_missing_secret_key_is_rejected(self):
        self.assert_secret_key_rejected(
            environment={}
        )

    def test_empty_secret_key_is_rejected(self):
        self.assert_secret_key_rejected(
            environment={
                "SECRET_KEY": "",
            }
        )

    def test_django_insecure_secret_key_is_rejected(self):
        self.assert_secret_key_rejected(
            environment={
                "SECRET_KEY": (
                    "django-insecure-"
                    "local-development-key"
                ),
            }
        )

    def test_weak_secret_key_is_rejected(self):
        self.assert_secret_key_rejected(
            environment={
                "SECRET_KEY": "a" * 50,
            }
        )

    def test_valid_secret_key_is_accepted(self):
        result = self._run_production_settings(
            environment={
                "SECRET_KEY": VALID_SECRET_KEY,
            },
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )
        self.assertIn(
            "IMPORTED",
            result.stdout,
        )

    def test_transport_security_defaults_are_safe(self):
        output_expression = """json.dumps({
    "session_cookie_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_cookie_secure": settings.CSRF_COOKIE_SECURE,
    "secure_ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "secure_hsts_seconds": settings.SECURE_HSTS_SECONDS,
    "secure_hsts_include_subdomains": (
        settings.SECURE_HSTS_INCLUDE_SUBDOMAINS
    ),
    "secure_hsts_preload": settings.SECURE_HSTS_PRELOAD,
})"""

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

        process_environment = os.environ.copy()

        for variable_name in SECURITY_ENVIRONMENT_VARIABLES:
            process_environment.pop(
                variable_name,
                None,
            )

        process_environment[
            "SECRET_KEY"
        ] = VALID_SECRET_KEY

        result = subprocess.run(
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

        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )

        settings_values = json.loads(
            result.stdout.strip()
        )

        self.assertIs(
            settings_values[
                "session_cookie_secure"
            ],
            True,
        )
        self.assertIs(
            settings_values[
                "csrf_cookie_secure"
            ],
            True,
        )
        self.assertIs(
            settings_values[
                "secure_ssl_redirect"
            ],
            True,
        )
        self.assertEqual(
            settings_values[
                "secure_hsts_seconds"
            ],
            3600,
        )
        self.assertIs(
            settings_values[
                "secure_hsts_include_subdomains"
            ],
            False,
        )
        self.assertIs(
            settings_values[
                "secure_hsts_preload"
            ],
            False,
        )
