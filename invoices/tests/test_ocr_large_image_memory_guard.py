from pathlib import Path

from django.test import SimpleTestCase


class OCRLargeImageMemoryGuardTests(SimpleTestCase):

    def setUp(self):
        self.source = Path(
            "ocr/services.py"
        ).read_text(
            encoding="utf-8"
        )

    def test_pdf_pages_are_rendered_one_by_one(self):
        self.assertIn(
            "first_page=page_number",
            self.source,
        )
        self.assertIn(
            "last_page=page_number",
            self.source,
        )
        self.assertIn(
            "thread_count=1",
            self.source,
        )
        self.assertIn(
            "grayscale=True",
            self.source,
        )

    def test_tesseract_has_timeout_and_total_call_guard(self):
        self.assertIn(
            "timeout=OCR_TESSERACT_TIMEOUT",
            self.source,
        )
        self.assertIn(
            "OCR_MAX_TESSERACT_CALLS",
            self.source,
        )
        self.assertIn(
            "tesseract_calls",
            self.source,
        )
        self.assertIn(
            "is_ocr_timeout_error",
            self.source,
        )

    def test_large_images_are_downscaled_before_ocr(self):
        self.assertIn(
            "MAX_OCR_IMAGE_PIXELS",
            self.source,
        )
        self.assertIn(
            "MAX_OCR_IMAGE_SIDE",
            self.source,
        )
        self.assertIn(
            "image.thumbnail(",
            self.source,
        )
        self.assertIn(
            "safe_prepare_image_for_ocr(",
            self.source,
        )

    def test_old_dangerous_dpi_values_are_not_used(self):
        self.assertNotIn(
            "dpi=300",
            self.source,
        )
        self.assertNotIn(
            "dpi=600",
            self.source,
        )

    def test_pdf_ocr_does_not_silently_continue_after_timeout(self):
        self.assertIn(
            "OCR остановлен по таймауту Tesseract",
            self.source,
        )
        self.assertNotIn(
            "except Exception:\n                    continue",
            self.source,
        )
