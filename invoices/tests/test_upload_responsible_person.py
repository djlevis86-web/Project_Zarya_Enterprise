from datetime import date
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice, ResponsiblePerson


class UploadResponsiblePersonTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="responsible-upload-user",
            email="responsible-upload@example.com",
            password="test-password",
        )
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Смолина Мария Александровна",
            is_active=True,
        )

    def test_invoice_model_allows_old_document_without_responsible(self):
        responsible_field = Invoice._meta.get_field(
            "responsible"
        )

        self.assertTrue(
            responsible_field.null
        )
        self.assertTrue(
            responsible_field.blank
        )

    def test_multi_upload_assigns_same_responsible_to_every_invoice(self):
        self.client.force_login(
            self.user
        )

        upload_url = reverse(
            "upload_invoice"
        )

        get_response = self.client.get(
            upload_url
        )

        self.assertEqual(
            get_response.status_code,
            200,
        )

        upload_token = self.client.session[
            "invoice_upload_token"
        ]

        first_file = SimpleUploadedFile(
            "first-invoice.pdf",
            b"%PDF-1.4\nfirst document\n",
            content_type="application/pdf",
        )
        second_file = SimpleUploadedFile(
            "second-invoice.pdf",
            b"%PDF-1.4\nsecond document\n",
            content_type="application/pdf",
        )

        with TemporaryDirectory() as media_root:
            with self.settings(
                MEDIA_ROOT=media_root
            ):
                response = self.client.post(
                    upload_url,
                    data={
                        "upload_token": upload_token,
                        "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
                        "title": "Пакет документов",
                        "description": "Тест ответственного",
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

        self.assertRedirects(
            response,
            reverse(
                "upload_result"
            ),
        )

        invoices = (
            Invoice.objects
            .filter(
                user=self.user
            )
            .order_by(
                "id"
            )
        )

        self.assertEqual(
            invoices.count(),
            2,
        )

        self.assertEqual(
            set(
                invoices.values_list(
                    "responsible_id",
                    flat=True,
                )
            ),
            {
                self.responsible.id,
            },
        )

        self.assertEqual(
            set(
                invoices.values_list(
                    "planned_payment_date",
                    flat=True,
                )
            ),
            {
                date(2026, 7, 30),
            },
        )

        self.assertEqual(
            set(
                invoices.values_list(
                    "original_filename",
                    flat=True,
                )
            ),
            {
                "first-invoice.pdf",
                "second-invoice.pdf",
            },
        )
