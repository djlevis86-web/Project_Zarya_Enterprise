from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from invoices.forms import UploadInvoiceForm
from invoices.models import Invoice, ResponsiblePerson


class UploadInvoiceFormSeparateValidationTests(TestCase):

    def setUp(self):
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Смолина Мария Александровна",
            is_active=True,
        )
        self.inactive_responsible = ResponsiblePerson.objects.create(
            full_name="Неактивный ответственный",
            is_active=False,
        )

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

    def _data(self, **overrides):
        data = {
            "document_type": "invoice",
            "title": "Аксютина Г.А.",
            "amount": "",
            "planned_payment_date": "2026-07-10",
            "responsible": str(
                self.responsible.id
            ),
            "description": "",
        }
        data.update(
            overrides
        )
        return data

    def test_upload_form_accepts_required_fields_without_amount(self):
        form = UploadInvoiceForm(
            data=self._data(
                document_type="",
            ),
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
            form.cleaned_data["planned_payment_date"],
            date(2026, 7, 10),
        )
        self.assertEqual(
            form.cleaned_data["responsible"],
            self.responsible,
        )
        self.assertEqual(
            len(form.cleaned_data["files"]),
            1,
        )

    def test_upload_form_requires_title(self):
        form = UploadInvoiceForm(
            data=self._data(
                title="",
            ),
            files=self._files(),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "title",
            form.errors,
        )

    def test_upload_form_requires_planned_payment_date(self):
        data = self._data()
        data.pop(
            "planned_payment_date"
        )

        form = UploadInvoiceForm(
            data=data,
            files=self._files(),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "planned_payment_date",
            form.errors,
        )

    def test_upload_form_requires_responsible(self):
        data = self._data()
        data.pop(
            "responsible"
        )

        form = UploadInvoiceForm(
            data=data,
            files=self._files(),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "responsible",
            form.errors,
        )

    def test_upload_form_rejects_inactive_responsible(self):
        form = UploadInvoiceForm(
            data=self._data(
                responsible=str(
                    self.inactive_responsible.id
                ),
            ),
            files=self._files(),
        )

        self.assertFalse(
            form.is_valid(),
        )
        self.assertIn(
            "responsible",
            form.errors,
        )

    def test_upload_form_lists_only_active_responsible_people(self):
        form = UploadInvoiceForm()

        responsible_ids = list(
            form.fields["responsible"]
            .queryset
            .values_list(
                "id",
                flat=True,
            )
        )

        self.assertIn(
            self.responsible.id,
            responsible_ids,
        )
        self.assertNotIn(
            self.inactive_responsible.id,
            responsible_ids,
        )

    def test_upload_form_requires_files(self):
        form = UploadInvoiceForm(
            data=self._data(),
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
            data=self._data(
                amount="12 345,67",
            ),
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
            data=self._data(),
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
