from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from invoices.models import (
    Invoice,
    InvoiceUploadBatch,
    OCRJob,
    ResponsiblePerson,
)
from users.permissions import user_can_upload_invoices


class InvoiceUploadPermissionTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.uploader = User.objects.create_user(
            username="upload-permission-uploader",
            email="upload-permission-uploader@example.com",
            password="pass12345",
            role=User.Role.USER,
        )

        self.manager = User.objects.create_user(
            username="upload-permission-manager",
            email="upload-permission-manager@example.com",
            password="pass12345",
            role=User.Role.MANAGER,
        )

        self.admin = User.objects.create_user(
            username="upload-permission-admin",
            email="upload-permission-admin@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )

        self.analyst = User.objects.create_user(
            username="upload-permission-analyst",
            email="upload-permission-analyst@example.com",
            password="pass12345",
            role=User.Role.ANALYST,
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный для теста прав загрузки",
            is_active=True,
        )

        self.url = reverse(
            "upload_invoice"
        )

    def test_upload_policy_allows_expected_roles(self):
        allowed_users = (
            self.uploader,
            self.manager,
            self.admin,
        )

        for user in allowed_users:
            with self.subTest(
                role=user.role
            ):
                self.assertTrue(
                    user_can_upload_invoices(
                        user
                    )
                )

    def test_upload_policy_denies_analyst(self):
        self.assertFalse(
            user_can_upload_invoices(
                self.analyst
            )
        )

    def test_allowed_roles_can_open_upload_form(self):
        allowed_users = (
            self.uploader,
            self.manager,
            self.admin,
        )

        for user in allowed_users:
            with self.subTest(
                role=user.role
            ):
                self.client.force_login(
                    user
                )

                response = self.client.get(
                    self.url
                )

                self.assertEqual(
                    response.status_code,
                    200,
                )

                self.client.logout()

    def test_analyst_cannot_open_upload_form(self):
        self.client.force_login(
            self.analyst
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            InvoiceUploadBatch.objects.count(),
            0,
        )
        self.assertEqual(
            Invoice.objects.count(),
            0,
        )
        self.assertEqual(
            OCRJob.objects.count(),
            0,
        )

    def test_analyst_cannot_submit_upload(self):
        self.client.force_login(
            self.analyst
        )

        session = self.client.session
        session[
            "invoice_upload_token"
        ] = "analyst-upload-token"
        session.save()

        first_file = SimpleUploadedFile(
            "analyst-first.pdf",
            b"%PDF-1.4\nfirst document\n",
            content_type="application/pdf",
        )

        second_file = SimpleUploadedFile(
            "analyst-second.pdf",
            b"%PDF-1.4\nsecond document\n",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            data={
                "upload_token": "analyst-upload-token",
                "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
                "title": "Analyst forbidden upload",
                "description": "Permission regression test",
                "amount": "",
                "planned_payment_date": "2026-07-30",
                "responsible": str(
                    self.responsible.id
                ),
                "files": [
                    first_file,
                    second_file,
                ],
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            InvoiceUploadBatch.objects.count(),
            0,
        )
        self.assertEqual(
            Invoice.objects.count(),
            0,
        )
        self.assertEqual(
            OCRJob.objects.count(),
            0,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse(
                "login"
            ),
            response.url,
        )
