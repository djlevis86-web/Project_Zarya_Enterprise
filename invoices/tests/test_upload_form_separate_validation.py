from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils.datastructures import MultiValueDict

from invoices.forms import UploadInvoiceForm
from invoices.models import Invoice


class UploadInvoiceFormSeparateValidationTests(SimpleTestCase):

    def _files(self, filename="invoice.pdf", content=b"%PDF-1.4\n"):
        return MultiValueDict(
            {
                "files": [
                    SimpleUploadedFile(
                        filename,
                        content,
                        content_type="application/pdf",
                    )
                ]
            }
        )

    def test_upload_form_accepts_required_title_and_files_without_amount(self):
        form = UploadInvoiceForm(
            data={
                "document_type": "",
                "title": "Аксютина Г.А.",
                "amount": "",
                "description": "",
            },
            files=self._files(),
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )
        self.assertEqual(
            form.cleaned_data["document_type"],
            Invoice.DOCUMENT_TYPE_INVOICE,
        )
        self.assertEqual(
            form.cleaned_data["title"],
            "Аксютина Г.А.",
        )
        self.assertIsNone(
            form.cleaned_data["amount"],
        )
        self.assertEqual(
            len(form.cleaned_data["files"]),
            1,
        )

    def test_upload_form_requires_title(self):
        form = UploadInvoiceForm(
            data={
                "document_type": "invoice",
                "title": "",
                "amount": "",
                "description": "",
            },
            files=self._files(),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "title",
            form.errors,
        )

    def test_upload_form_requires_files(self):
        form = UploadInvoiceForm(
            data={
                "document_type": "invoice",
                "title": "Аксютина Г.А.",
                "amount": "",
                "description": "",
            },
            files=MultiValueDict(),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "files",
            form.errors,
        )

    def test_upload_form_parses_comma_amount(self):
        form = UploadInvoiceForm(
            data={
                "document_type": "invoice",
                "title": "Аксютина Г.А.",
                "amount": "12 345,67",
                "description": "",
            },
            files=self._files(),
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )
        self.assertEqual(
            form.cleaned_data["amount"],
            Decimal("12345.67"),
        )

    def test_upload_form_rejects_bad_extension(self):
        form = UploadInvoiceForm(
            data={
                "document_type": "invoice",
                "title": "Аксютина Г.А.",
                "amount": "",
                "description": "",
            },
            files=self._files(
                filename="bad.txt",
                content=b"bad",
            ),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "files",
            form.errors,
        )
