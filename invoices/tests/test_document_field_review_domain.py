from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.document_field_review_service import (
    confirm_invoice_field,
    sync_manual_field_review,
    sync_ocr_field_review,
)
from invoices.models import (
    Counterparty,
    Invoice,
    InvoiceFieldReview,
    ResponsiblePerson,
)
from invoices.ocr_processing_service import apply_ocr_identity_to_invoice
from invoices.presentation_services import annotate_invoice_workspace
from invoices.readiness_services import evaluate_document_readiness


class DocumentFieldReviewDomainTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="field-review-staff",
            email="field-review-staff@example.com",
            password="test-password",
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="field-review-regular",
            email="field-review-regular@example.com",
            password="test-password",
        )
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный по документу",
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО Проверенный поставщик",
            source=Counterparty.SOURCE_MANUAL,
        )
        self.invoice = Invoice.objects.create(
            user=self.staff,
            title="Документ проверки полей",
            file="invoices/field-review.pdf",
            amount=Decimal("1000.00"),
            ocr_amount=Decimal("1000.00"),
            amount_verified=True,
            invoice_number="A-100",
            invoice_date="31.07.2026",
            document_date=date(2026, 7, 31),
            vendor="ООО Проверенный поставщик",
            counterparty=self.counterparty,
            responsible=self.responsible,
        )

    def test_confirmed_number_survives_repeat_ocr(self):
        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_INVOICE_NUMBER,
            self.staff,
        )

        warning = apply_ocr_identity_to_invoice(
            self.invoice,
            {
                "invoice_number": "OCR-999",
                "invoice_date": "01.08.2026",
                "document_date": date(2026, 8, 1),
                "vendor": "ООО Новый OCR поставщик",
                "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            },
        )
        self.invoice.save()
        sync_ocr_field_review(
            self.invoice,
            InvoiceFieldReview.FIELD_INVOICE_NUMBER,
            "OCR-999",
        )

        self.assertEqual(warning, "")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_number, "A-100")
        review = InvoiceFieldReview.objects.get(
            invoice=self.invoice,
            field_name=InvoiceFieldReview.FIELD_INVOICE_NUMBER,
        )
        self.assertTrue(review.is_confirmed)
        self.assertEqual(review.confirmed_value, "A-100")
        self.assertEqual(review.recognized_value, "OCR-999")

    def test_confirmed_date_and_vendor_survive_repeat_ocr(self):
        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_DOCUMENT_DATE,
            self.staff,
        )
        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
            self.staff,
        )

        apply_ocr_identity_to_invoice(
            self.invoice,
            {
                "invoice_number": "OCR-300",
                "invoice_date": "03.08.2026",
                "document_date": date(2026, 8, 3),
                "vendor": "ООО OCR перезапись",
                "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            },
        )

        self.assertEqual(
            self.invoice.document_date,
            date(2026, 7, 31),
        )
        self.assertEqual(
            self.invoice.vendor,
            "ООО Проверенный поставщик",
        )

    def test_unconfirmed_number_is_updated_by_repeat_ocr(self):
        apply_ocr_identity_to_invoice(
            self.invoice,
            {
                "invoice_number": "OCR-200",
                "invoice_date": "02.08.2026",
                "document_date": date(2026, 8, 2),
                "vendor": "ООО OCR",
                "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            },
        )
        self.assertEqual(self.invoice.invoice_number, "OCR-200")
        self.assertEqual(self.invoice.document_date, date(2026, 8, 2))
        self.assertEqual(self.invoice.vendor, "ООО OCR")

    def test_manual_change_invalidates_previous_confirmation(self):
        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
            self.staff,
        )
        self.invoice.vendor = "ООО Исправленный поставщик"
        self.invoice.save(update_fields=["vendor", "updated_at"])
        review = sync_manual_field_review(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
        )

        self.assertFalse(review.is_confirmed)
        self.assertEqual(review.current_value, "ООО Исправленный поставщик")
        self.assertEqual(review.confirmed_value, "")
        self.assertIsNone(review.confirmed_by)
        self.assertIsNone(review.confirmed_at)

    def test_amount_confirmation_keeps_legacy_readiness_contract(self):
        self.invoice.amount_verified = False
        self.invoice.ocr_verified = False
        self.invoice.save(
            update_fields=[
                "amount_verified",
                "ocr_verified",
                "updated_at",
            ]
        )
        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_AMOUNT,
            self.staff,
        )
        annotated = annotate_invoice_workspace(
            Invoice.objects.filter(pk=self.invoice.pk)
        ).get()
        readiness = evaluate_document_readiness(annotated)

        self.assertTrue(annotated.amount_verified)
        self.assertTrue(annotated.field_review_amount_confirmed)
        self.assertNotIn(
            "amount_unverified",
            {issue.code for issue in readiness.blockers},
        )

    def test_staff_post_endpoint_confirms_one_field(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse(
                "confirm_invoice_field",
                kwargs={
                    "invoice_id": self.invoice.id,
                    "field_name": InvoiceFieldReview.FIELD_DOCUMENT_DATE,
                },
            ),
            {
                "value": "2026-08-05",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.document_date, date(2026, 8, 5))
        review = InvoiceFieldReview.objects.get(
            invoice=self.invoice,
            field_name=InvoiceFieldReview.FIELD_DOCUMENT_DATE,
        )
        self.assertTrue(review.is_confirmed)
        self.assertEqual(review.confirmed_value, "2026-08-05")
        self.assertEqual(review.confirmed_by, self.staff)
        self.assertIsNotNone(review.confirmed_at)

    def test_confirmation_endpoint_is_post_only_and_staff_only(self):
        url = reverse(
            "confirm_invoice_field",
            kwargs={
                "invoice_id": self.invoice.id,
                "field_name": InvoiceFieldReview.FIELD_VENDOR,
            },
        )
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.force_login(self.regular)
        response = self.client.post(url, {"value": "ООО Новое имя"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
