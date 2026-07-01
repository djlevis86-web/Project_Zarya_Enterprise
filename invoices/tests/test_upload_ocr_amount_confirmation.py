from decimal import Decimal

from django.test import TestCase

from invoices.models import Invoice
from invoices.ocr_verification_service import apply_ocr_amount_to_invoice


class UploadOCRAmountConfirmationTests(TestCase):
    def test_ocr_amount_can_be_used_as_confirmed_amount(self):
        invoice = Invoice(
            title="OCR confirmed amount test",
            amount=Decimal("123.45"),
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "987.65",
            use_ocr_as_confirmed_amount=True,
        )

        self.assertEqual(warning, "")
        self.assertEqual(invoice.ocr_amount, Decimal("987.65"))
        self.assertEqual(invoice.amount, Decimal("987.65"))
        self.assertTrue(invoice.amount_verified)
        self.assertTrue(invoice.ocr_verified)

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

    def test_zero_amount_is_filled_from_ocr_by_default(self):
        invoice = Invoice(
            title="OCR zero amount test",
            amount=Decimal("0.00"),
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "987.65",
        )

        self.assertEqual(warning, "")
        self.assertEqual(invoice.ocr_amount, Decimal("987.65"))
        self.assertEqual(invoice.amount, Decimal("987.65"))
        self.assertTrue(invoice.amount_verified)
        self.assertTrue(invoice.ocr_verified)
