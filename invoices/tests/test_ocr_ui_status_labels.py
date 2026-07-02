from pathlib import Path

from django.test import SimpleTestCase


class OCRUIStatusLabelsTemplateTests(SimpleTestCase):

    def setUp(self):
        self.invoice_list = Path(
            "templates/invoices/invoice_list.html"
        ).read_text(
            encoding="utf-8"
        )

        self.payment_registry = Path(
            "templates/invoices/payment_registry.html"
        ).read_text(
            encoding="utf-8"
        )

    def test_invoice_list_distinguishes_ocr_text_without_amount(self):
        self.assertIn(
            "{% elif invoice.ocr_text %}",
            self.invoice_list,
        )
        self.assertIn(
            "OCR выполнен, сумма не найдена",
            self.invoice_list,
        )

    def test_invoice_list_keeps_ocr_not_done_state(self):
        self.assertIn(
            "OCR не выполнен",
            self.invoice_list,
        )

    def test_payment_registry_distinguishes_item_ocr_text_without_amount(self):
        self.assertIn(
            "{% elif item.invoice.ocr_text %}",
            self.payment_registry,
        )
        self.assertIn(
            "Оплата заблокирована: сумма не найдена",
            self.payment_registry,
        )

    def test_payment_registry_distinguishes_source_invoice_ocr_text_without_amount(self):
        self.assertIn(
            "{% elif invoice.ocr_text %}",
            self.payment_registry,
        )
        self.assertIn(
            "Оплата заблокирована: OCR не выполнен",
            self.payment_registry,
        )

    def test_payment_registry_keeps_verified_and_requires_review_states(self):
        self.assertIn(
            "Сумма подтверждена",
            self.payment_registry,
        )
        self.assertIn(
            "Сумма требует проверки",
            self.payment_registry,
        )
