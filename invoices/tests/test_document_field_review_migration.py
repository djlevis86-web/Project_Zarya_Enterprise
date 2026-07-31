from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.models import Invoice, InvoiceFieldReview


class DocumentFieldReviewMigrationTests(TestCase):
    def test_data_migration_backfills_four_review_rows(self):
        user = get_user_model().objects.create_user(
            username="field-review-migration",
            password="test-password",
        )
        invoice = Invoice.objects.create(
            user=user,
            title="Legacy invoice",
            file="invoices/legacy-review.pdf",
            amount=Decimal("1234.50"),
            ocr_amount=Decimal("1200.00"),
            amount_verified=True,
            invoice_number="LEGACY-77",
            invoice_date="31.07.2026",
            vendor="ООО Legacy",
        )

        InvoiceFieldReview.objects.all().delete()
        migration = import_module(
            "invoices.migrations.0028_invoicefieldreview"
        )
        migration.populate_field_reviews(apps, None)

        reviews = {
            review.field_name: review
            for review in InvoiceFieldReview.objects.filter(
                invoice=invoice
            )
        }
        self.assertEqual(
            set(reviews),
            {
                InvoiceFieldReview.FIELD_AMOUNT,
                InvoiceFieldReview.FIELD_INVOICE_NUMBER,
                InvoiceFieldReview.FIELD_DOCUMENT_DATE,
                InvoiceFieldReview.FIELD_VENDOR,
            },
        )

        amount_review = reviews[InvoiceFieldReview.FIELD_AMOUNT]
        self.assertEqual(amount_review.recognized_value, "1200.00")
        self.assertEqual(amount_review.current_value, "1234.50")
        self.assertEqual(amount_review.confirmed_value, "1234.50")
        self.assertTrue(amount_review.is_confirmed)
        self.assertIsNotNone(amount_review.confirmed_at)

        number_review = reviews[
            InvoiceFieldReview.FIELD_INVOICE_NUMBER
        ]
        self.assertEqual(number_review.recognized_value, "LEGACY-77")
        self.assertEqual(number_review.current_value, "LEGACY-77")
        self.assertFalse(number_review.is_confirmed)
