from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from invoices.models import Invoice
from invoices.ocr_processing_service import run_invoice_ocr_processing


class OCRLightFallbackProcessingTests(TestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.temp_dir.name
        )
        self.override.enable()

        User = get_user_model()

        self.user = User.objects.create_user(
            username="ocr-light-user",
            email="ocr-light-user@example.com",
            password="pass12345",
        )

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()

    def create_invoice(self, filename="light-test.pdf"):
        return Invoice.objects.create(
            user=self.user,
            title="LIGHT OCR TEST INVOICE",
            amount=Decimal("0.00"),
            status=Invoice.STATUS_NEW,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            document_date=date(2026, 7, 1),
            file=SimpleUploadedFile(
                filename,
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
        )

    @patch(
        "invoices.ocr_processing_service.extract_text_from_pdf"
    )
    @patch(
        "invoices.ocr_processing_service.extract_text_from_pdf_light"
    )
    def test_light_ocr_fallback_saves_text_after_pdf_timeout(
        self,
        extract_text_from_pdf_light_mock,
        extract_text_from_pdf_mock,
    ):
        invoice = self.create_invoice()

        extract_text_from_pdf_mock.side_effect = RuntimeError(
            "OCR остановлен по таймауту Tesseract."
        )
        extract_text_from_pdf_light_mock.return_value = (
            "Счет на оплату № 09 от 24 июня 2026\n"
            "Поставщик: Индивидуальный предприниматель Беляев Андрей Александрович\n"
            "ИНН 350700661870\n"
            "Итого 1000,00"
        )

        ok, message = run_invoice_ocr_processing(
            invoice,
            self.user,
            "OCR выполнен из теста",
        )

        self.assertTrue(
            ok
        )
        self.assertEqual(
            message,
            "OCR успешно обновлен облегчённым режимом",
        )

        invoice.refresh_from_db()

        self.assertIn(
            "Счет на оплату",
            invoice.ocr_text,
        )
        self.assertIn(
            "облегчённым режимом",
            invoice.ocr_comment,
        )

        extract_text_from_pdf_light_mock.assert_called_once()

    @patch(
        "invoices.ocr_processing_service.extract_text_from_pdf"
    )
    def test_waybill_document_type_is_saved_after_ocr(
        self,
        extract_text_from_pdf_mock,
    ):
        invoice = self.create_invoice(
            filename="waybill-test.pdf"
        )

        extract_text_from_pdf_mock.return_value = (
            "Товарная накладная № 45 от 01.07.2026\n"
            "Поставщик: ООО РОМАШКА\n"
            "Итого 1250,00"
        )

        ok, _message = run_invoice_ocr_processing(
            invoice,
            self.user,
            "OCR выполнен из теста",
        )

        self.assertTrue(
            ok
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.document_type,
            Invoice.DOCUMENT_TYPE_WAYBILL,
        )
        self.assertEqual(
            invoice.invoice_number,
            "45",
        )
        self.assertEqual(
            invoice.ocr_text,
            extract_text_from_pdf_mock.return_value,
        )
