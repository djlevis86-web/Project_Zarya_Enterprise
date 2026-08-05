from __future__ import annotations

import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from invoices.management.commands.seed_demo_data import (
    DEMO_PREFIX,
    PROFILES,
)
from invoices.models import (
    Counterparty,
    Invoice,
    PaymentRegistry,
    ResponsiblePerson,
)


class SeedDemoDataCommandTests(TestCase):
    def setUp(self) -> None:
        self.temporary_media = tempfile.TemporaryDirectory()
        self.addCleanup(
            self.temporary_media.cleanup
        )
        User = get_user_model()
        self.actor = User.objects.create_user(
            username="demo_seed_admin",
            email="demo-seed-admin@example.invalid",
            password="StrongLocalOnlyPassword-2026",
            role="ADMIN",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )

    def _settings(self):
        return override_settings(
            DEBUG=True,
            BASE_DIR=Path(r"D:\Project_Zarya"),
            MEDIA_ROOT=self.temporary_media.name,
        )

    def test_command_rejects_missing_safety_flag(self) -> None:
        with self._settings():
            with patch.dict(
                os.environ,
                {
                    "ALLOW_DEMO_SEED": "",
                },
                clear=False,
            ):
                with self.assertRaises(CommandError):
                    call_command(
                        "seed_demo_data",
                        "--dry-run",
                        stdout=StringIO(),
                    )

    def test_small_profile_is_deterministic_and_resettable(
        self,
    ) -> None:
        plan = PROFILES["small"]
        marker = f"{DEMO_PREFIX}20260805]"
        output = StringIO()

        with self._settings():
            with patch.dict(
                os.environ,
                {
                    "ALLOW_DEMO_SEED": "1",
                },
                clear=False,
            ):
                call_command(
                    "seed_demo_data",
                    "--profile",
                    "small",
                    "--seed",
                    "20260805",
                    stdout=output,
                )

                self.assertEqual(
                    Invoice.objects.filter(
                        title__startswith=marker,
                    ).count(),
                    plan.total_documents,
                )
                self.assertEqual(
                    PaymentRegistry.objects.filter(
                        title__startswith=marker,
                    ).count(),
                    plan.history_registries + 1,
                )
                self.assertEqual(
                    Counterparty.objects.filter(
                        external_id_1c__startswith=(
                            "DEMO-ZARYA-"
                        ),
                    ).count(),
                    plan.counterparties,
                )
                self.assertEqual(
                    ResponsiblePerson.objects.filter(
                        full_name__startswith=marker,
                    ).count(),
                    plan.responsible_people,
                )

                call_command(
                    "seed_demo_data",
                    "--profile",
                    "small",
                    "--seed",
                    "20260805",
                    "--validate-only",
                    stdout=StringIO(),
                )

                with self.assertRaises(CommandError):
                    call_command(
                        "seed_demo_data",
                        "--profile",
                        "small",
                        "--seed",
                        "20260805",
                        stdout=StringIO(),
                    )

                call_command(
                    "seed_demo_data",
                    "--reset",
                    stdout=StringIO(),
                )

        self.assertFalse(
            Invoice.objects.filter(
                title__startswith=DEMO_PREFIX,
            ).exists()
        )
        self.assertFalse(
            PaymentRegistry.objects.filter(
                title__startswith=DEMO_PREFIX,
            ).exists()
        )
        self.assertFalse(
            Counterparty.objects.filter(
                external_id_1c__startswith=(
                    "DEMO-ZARYA-"
                ),
            ).exists()
        )

    def test_dry_run_does_not_write_database(self) -> None:
        output = StringIO()

        with self._settings():
            with patch.dict(
                os.environ,
                {
                    "ALLOW_DEMO_SEED": "1",
                },
                clear=False,
            ):
                call_command(
                    "seed_demo_data",
                    "--profile",
                    "visual",
                    "--seed",
                    "20260805",
                    "--dry-run",
                    stdout=output,
                )

        self.assertFalse(
            Invoice.objects.filter(
                title__startswith=DEMO_PREFIX,
            ).exists()
        )
        self.assertIn(
            "TOTAL DOCUMENTS: 228",
            output.getvalue(),
        )
        self.assertIn(
            "DATABASE WRITES: NONE",
            output.getvalue(),
        )
