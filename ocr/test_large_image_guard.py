from django.test import SimpleTestCase
from PIL import Image

from ocr.services import MAX_OCR_IMAGE_SIDE, safe_prepare_image_for_ocr


class LargeImageGuardTests(SimpleTestCase):

    def test_large_side_image_is_resized_before_ocr(self):
        image = Image.new(
            "RGB",
            (
                MAX_OCR_IMAGE_SIDE + 1000,
                100,
            ),
            "white",
        )

        prepared = safe_prepare_image_for_ocr(
            image
        )

        self.assertLessEqual(
            prepared.size[0],
            MAX_OCR_IMAGE_SIDE,
        )
