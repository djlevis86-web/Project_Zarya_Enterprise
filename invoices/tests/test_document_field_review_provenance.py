from datetime import date
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.document_field_review_service import (
    build_invoice_field_review_workspace,
    sync_ocr_field_review,
)
from invoices.models import Counterparty, Invoice, InvoiceFieldReview


class DocumentFieldReviewProvenanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="provenance-user",
            email="provenance-user@example.com",
            password="test-password",
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО Эталон 1С",
            inn="7800000000",
            source=Counterparty.SOURCE_1C,
        )
        self.invoice = Invoice.objects.create(
            user=self.user,
            title="Документ provenance",
            file="invoices/provenance.pdf",
            amount=Decimal("1000.00"),
            ocr_amount=Decimal("990.00"),
            invoice_number="SYS-1",
            document_date=date(2026, 8, 1),
            vendor="ООО Текущее",
            counterparty=self.counterparty,
        )

    def test_legacy_current_value_is_not_claimed_as_document_evidence(self):
        InvoiceFieldReview.objects.create(
            invoice=self.invoice,
            field_name=InvoiceFieldReview.FIELD_INVOICE_NUMBER,
            recognized_value="SYS-1",
            recognized_source=InvoiceFieldReview.SOURCE_LEGACY_CURRENT,
            current_value="SYS-1",
        )

        workspace = build_invoice_field_review_workspace(
            self.invoice,
            self.invoice.field_reviews.select_related("confirmed_by"),
        )
        row = next(
            item
            for item in workspace["rows"]
            if item["field_name"] == InvoiceFieldReview.FIELD_INVOICE_NUMBER
        )

        self.assertFalse(row["recognized_is_document_evidence"])
        self.assertEqual(row["recognized_value"], "")
        self.assertEqual(row["raw_recognized_value"], "SYS-1")
        self.assertEqual(row["status_code"], "unrecognized")
        self.assertEqual(row["status_label"], "Источник не подтверждён")

    def test_runtime_ocr_sync_records_exact_source_and_time(self):
        review = sync_ocr_field_review(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
            "ООО Из документа",
        )

        self.assertEqual(review.recognized_source, InvoiceFieldReview.SOURCE_OCR)
        self.assertIsNotNone(review.recognized_at)
        self.assertEqual(review.recognized_value, "ООО Из документа")

    def test_vendor_workspace_exposes_1c_reference_without_changing_invoice(self):
        InvoiceFieldReview.objects.create(
            invoice=self.invoice,
            field_name=InvoiceFieldReview.FIELD_VENDOR,
            recognized_value="ООО Из документа",
            recognized_source=InvoiceFieldReview.SOURCE_OCR,
            current_value="ООО Текущее",
        )

        workspace = build_invoice_field_review_workspace(
            self.invoice,
            self.invoice.field_reviews.select_related("confirmed_by"),
        )
        row = next(
            item
            for item in workspace["rows"]
            if item["field_name"] == InvoiceFieldReview.FIELD_VENDOR
        )

        self.assertTrue(row["reference_available"])
        self.assertEqual(row["reference_value"], "ООО Эталон 1С")
        self.assertEqual(row["reference_source_label"], "Справочник 1С")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.vendor, "ООО Текущее")


class DocumentFieldReviewProvenanceMigrationTests(TestCase):
    def test_existing_rows_are_classified_conservatively(self):
        user = get_user_model().objects.create_user(
            username="provenance-migration",
            email="provenance-migration@example.com",
            password="test-password",
        )
        invoice = Invoice.objects.create(
            user=user,
            title="Legacy provenance",
            file="invoices/legacy-provenance.pdf",
            amount=Decimal("1000.00"),
            ocr_amount=Decimal("990.00"),
            invoice_number="CURRENT-1",
            vendor="ООО Current",
        )
        amount = InvoiceFieldReview.objects.create(
            invoice=invoice,
            field_name=InvoiceFieldReview.FIELD_AMOUNT,
            recognized_value="990.00",
            current_value="1000.00",
        )
        number = InvoiceFieldReview.objects.create(
            invoice=invoice,
            field_name=InvoiceFieldReview.FIELD_INVOICE_NUMBER,
            recognized_value="CURRENT-1",
            current_value="CURRENT-1",
        )
        vendor = InvoiceFieldReview.objects.create(
            invoice=invoice,
            field_name=InvoiceFieldReview.FIELD_VENDOR,
            recognized_value="ООО OCR",
            current_value="ООО Current",
        )
        date_review = InvoiceFieldReview.objects.create(
            invoice=invoice,
            field_name=InvoiceFieldReview.FIELD_DOCUMENT_DATE,
            recognized_value="",
            current_value="",
        )

        migration = import_module(
            "invoices.migrations.0029_invoicefieldreview_recognized_provenance"
        )
        migration.classify_existing_review_sources(apps, None)

        for review in (amount, number, vendor, date_review):
            review.refresh_from_db()
        self.assertEqual(
            amount.recognized_source,
            InvoiceFieldReview.SOURCE_LEGACY_OCR,
        )
        self.assertEqual(
            number.recognized_source,
            InvoiceFieldReview.SOURCE_LEGACY_CURRENT,
        )
        self.assertEqual(
            vendor.recognized_source,
            InvoiceFieldReview.SOURCE_LEGACY_OCR,
        )
        self.assertEqual(
            date_review.recognized_source,
            InvoiceFieldReview.SOURCE_UNKNOWN,
        )
