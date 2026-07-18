import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import (
    Client,
    TestCase,
    override_settings,
)
from django.urls import reverse


class BackupHTTPSafetyTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.admin_user = User.objects.create_user(
            username="backup-http-safety-admin",
            email="backup-http-safety@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
            is_staff=False,
            is_superuser=False,
        )

        self.client.force_login(
            self.admin_user
        )

        self.csrf_client = Client(
            enforce_csrf_checks=True
        )
        self.csrf_client.force_login(
            self.admin_user
        )

    def _get_csrf_token(self):
        response = self.csrf_client.get(
            reverse(
                "backups_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        return self.csrf_client.cookies[
            "csrftoken"
        ].value

    def test_create_backup_get_returns_405_without_calling_service(self):
        with patch(
            "system.views.create_database_backup"
        ) as create_backup_mock:
            response = self.client.get(
                reverse(
                    "create_backup"
                )
            )

        self.assertEqual(
            response.status_code,
            405,
        )
        create_backup_mock.assert_not_called()

    def test_delete_backup_get_returns_405_without_deleting_file(self):
        with tempfile.TemporaryDirectory(
            prefix="zarya-test-backup-get-"
        ) as temporary_directory:
            temporary_base = Path(
                temporary_directory
            )

            backups_directory = (
                temporary_base
                / "backups_db"
            )
            backups_directory.mkdir()

            filename = "backup-get-must-not-delete.sqlite3"
            backup_file = (
                backups_directory
                / filename
            )
            backup_file.write_bytes(
                b"backup-get-test"
            )

            with override_settings(
                BASE_DIR=temporary_base
            ):
                response = self.client.get(
                    reverse(
                        "delete_backup",
                        kwargs={
                            "filename": filename,
                        },
                    )
                )

            self.assertEqual(
                response.status_code,
                405,
            )
            self.assertTrue(
                backup_file.exists()
            )

    def test_create_backup_post_requires_csrf(self):
        with patch(
            "system.views.create_database_backup"
        ) as create_backup_mock:
            response = self.csrf_client.post(
                reverse(
                    "create_backup"
                )
            )

        self.assertEqual(
            response.status_code,
            403,
        )
        create_backup_mock.assert_not_called()

    def test_delete_backup_post_requires_csrf_without_deleting_file(self):
        with tempfile.TemporaryDirectory(
            prefix="zarya-test-backup-csrf-"
        ) as temporary_directory:
            temporary_base = Path(
                temporary_directory
            )

            backups_directory = (
                temporary_base
                / "backups_db"
            )
            backups_directory.mkdir()

            filename = "backup-csrf-must-not-delete.sqlite3"
            backup_file = (
                backups_directory
                / filename
            )
            backup_file.write_bytes(
                b"backup-csrf-test"
            )

            with override_settings(
                BASE_DIR=temporary_base
            ):
                response = self.csrf_client.post(
                    reverse(
                        "delete_backup",
                        kwargs={
                            "filename": filename,
                        },
                    )
                )

            self.assertEqual(
                response.status_code,
                403,
            )
            self.assertTrue(
                backup_file.exists()
            )

    def test_create_backup_post_with_csrf_calls_service(self):
        csrf_token = self._get_csrf_token()

        with (
            patch(
                "system.views.create_database_backup",
                return_value="backup-created.sqlite3",
            ) as create_backup_mock,
            patch(
                "system.views.log_action"
            ),
        ):
            response = self.csrf_client.post(
                reverse(
                    "create_backup"
                ),
                data={
                    "csrfmiddlewaretoken": csrf_token,
                },
            )

        self.assertRedirects(
            response,
            reverse(
                "system_dashboard"
            ),
            fetch_redirect_response=False,
        )
        create_backup_mock.assert_called_once_with()

    def test_delete_backup_post_with_csrf_deletes_file(self):
        csrf_token = self._get_csrf_token()

        with tempfile.TemporaryDirectory(
            prefix="zarya-test-backup-post-"
        ) as temporary_directory:
            temporary_base = Path(
                temporary_directory
            )

            backups_directory = (
                temporary_base
                / "backups_db"
            )
            backups_directory.mkdir()

            filename = "backup-post-delete.sqlite3"
            backup_file = (
                backups_directory
                / filename
            )
            backup_file.write_bytes(
                b"backup-post-test"
            )

            with (
                override_settings(
                    BASE_DIR=temporary_base
                ),
                patch(
                    "system.views.log_action"
                ),
            ):
                response = self.csrf_client.post(
                    reverse(
                        "delete_backup",
                        kwargs={
                            "filename": filename,
                        },
                    ),
                    data={
                        "csrfmiddlewaretoken": csrf_token,
                    },
                )

            self.assertRedirects(
                response,
                reverse(
                    "backups_list"
                ),
                fetch_redirect_response=False,
            )
            self.assertFalse(
                backup_file.exists()
            )
