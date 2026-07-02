from decimal import Decimal

from django.test import TestCase

from invoices.models import Invoice
from invoices.ocr_verification_service import apply_ocr_amount_to_invoice


class UploadOCRAmountConfirmationTests(TestCase):
    def test_upload_ocr_amount_is_prefilled_but_not_auto_verified(self):
        invoice = Invoice(
            title="OCR prefill amount test",
            amount=Decimal("123.45"),
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "987.65",
            prefill_amount_from_ocr=True,
        )

        self.assertIn("Требуется ручное подтверждение", warning)
        self.assertEqual(invoice.ocr_amount, Decimal("987.65"))
        self.assertEqual(invoice.amount, Decimal("987.65"))
        self.assertFalse(invoice.amount_verified)
        self.assertFalse(invoice.ocr_verified)

    def test_existing_amount_is_only_compared_by_default(self):
        invoice = Invoice(
            title="OCR compare amount test",
            amount=Decimal("123.45"),
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "987.65",
        )

        self.assertEqual(warning, "")
        self.assertEqual(invoice.ocr_amount, Decimal("987.65"))
        self.assertEqual(invoice.amount, Decimal("123.45"))
        self.assertFalse(invoice.amount_verified)
        self.assertFalse(invoice.ocr_verified)

    def test_existing_amount_matching_ocr_requires_manual_confirmation(self):
        invoice = Invoice(
            title="OCR matching amount test",
            amount=Decimal("987.65"),
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "987.65",
        )

        self.assertIn("Требуется ручное подтверждение", warning)
        self.assertEqual(invoice.ocr_amount, Decimal("987.65"))
        self.assertEqual(invoice.amount, Decimal("987.65"))
        self.assertFalse(invoice.amount_verified)
        self.assertFalse(invoice.ocr_verified)

    def test_zero_amount_is_prefilled_but_requires_manual_confirmation(self):
        invoice = Invoice(
            title="OCR zero amount test",
            amount=Decimal("0.00"),
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "987.65",
        )

        self.assertIn("Требуется ручное подтверждение", warning)
        self.assertEqual(invoice.ocr_amount, Decimal("987.65"))
        self.assertEqual(invoice.amount, Decimal("987.65"))
        self.assertFalse(invoice.amount_verified)
        self.assertFalse(invoice.ocr_verified)
