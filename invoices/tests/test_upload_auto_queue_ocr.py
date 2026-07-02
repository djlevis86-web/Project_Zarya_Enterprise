from pathlib import Path

from django.test import SimpleTestCase


class UploadAutoQueueOCRTests(SimpleTestCase):

    def test_upload_delayed_ocr_creates_ocr_job(self):
        source = Path(
            "invoices/view_modules/invoice_upload_views.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "from ..models import Invoice, InvoiceUploadBatch, OCRJob",
            source,
        )

        self.assertIn(
            "def enqueue_upload_ocr_job(invoice, user):",
            source,
        )

        self.assertIn(
            "OCRJob.objects.create",
            source,
        )

        self.assertIn(
            "status=OCRJob.STATUS_PENDING",
            source,
        )

        self.assertIn(
            "source='upload'",
            source,
        )

        self.assertIn(
            "ocr_job, ocr_job_created = enqueue_upload_ocr_job(",
            source,
        )

        self.assertIn(
            "OCR поставлен в очередь",
            source,
        )

    def test_upload_view_keeps_inline_ocr_safety_condition(self):
        source = Path(
            "invoices/view_modules/invoice_upload_views.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "len(files) > 1",
            source,
        )

        self.assertIn(
            "INLINE_OCR_MAX_FILE_SIZE_BYTES",
            source,
        )

        self.assertIn(
            "continue",
            source,
        )
