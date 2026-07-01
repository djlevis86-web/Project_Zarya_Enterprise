from pathlib import Path

from django.test import SimpleTestCase


class OCRRuntimeConfigTests(SimpleTestCase):
    def test_ocr_services_do_not_contain_hardcoded_local_ocr_paths(self):
        source = Path("ocr/services.py").read_text(
            encoding="utf-8",
        )

        self.assertNotIn(
            "C:\\Program Files\\Tesseract-OCR",
            source,
        )
        self.assertNotIn(
            "D:\\Release-26.02.0-0",
            source,
        )

    def test_ocr_services_import_without_local_ocr_binaries(self):
        import ocr.services

        self.assertTrue(
            hasattr(
                ocr.services,
                "extract_text_from_pdf",
            )
        )
        self.assertTrue(
            hasattr(
                ocr.services,
                "extract_text_from_image",
            )
        )
