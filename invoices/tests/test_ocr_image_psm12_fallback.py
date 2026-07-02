from pathlib import Path

from django.test import SimpleTestCase


class OCRImagePSM12FallbackTests(SimpleTestCase):

    def setUp(self):
        self.source = Path(
            "ocr/services.py"
        ).read_text(
            encoding="utf-8"
        )

        start = self.source.index(
            "def extract_text_from_image(image_path):"
        )

        end = self.source.index(
            "def clean_invoice_number(value):"
        )

        self.image_ocr_source = self.source[
            start:end
        ]

    def test_image_ocr_tries_psm_12_before_psm_6(self):
        psm_12_index = self.image_ocr_source.index(
            '"--oem 3 --psm 12"'
        )
        psm_6_index = self.image_ocr_source.index(
            '"--oem 3 --psm 6"'
        )

        self.assertLess(
            psm_12_index,
            psm_6_index,
        )

    def test_image_ocr_uses_normal_and_hard_preprocessors(self):
        self.assertIn(
            "preprocess_image,",
            self.image_ocr_source,
        )
        self.assertIn(
            "preprocess_image_hard,",
            self.image_ocr_source,
        )

    def test_image_ocr_selects_best_text_by_score(self):
        self.assertIn(
            "variants = []",
            self.image_ocr_source,
        )
        self.assertIn(
            "best_text = max(",
            self.image_ocr_source,
        )
        self.assertIn(
            "key=ocr_score",
            self.image_ocr_source,
        )
        self.assertIn(
            ") >= 85:",
            self.image_ocr_source,
        )

    def test_image_ocr_continues_after_timeout_variant(self):
        self.assertIn(
            "except Exception as error:",
            self.image_ocr_source,
        )
        self.assertIn(
            "is_ocr_timeout_error(",
            self.image_ocr_source,
        )
        self.assertIn(
            "continue",
            self.image_ocr_source,
        )

    def test_image_ocr_uses_safe_prepare_before_preprocessing(self):
        self.assertIn(
            "safe_prepare_image_for_ocr(",
            self.image_ocr_source,
        )
        self.assertIn(
            "base_image = image.copy()",
            self.image_ocr_source,
        )
