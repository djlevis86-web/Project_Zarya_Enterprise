from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class OCRDiagnosticsCommandTests(SimpleTestCase):
    def test_ocr_diagnostics_reports_missing_dependencies(self):
        output = StringIO()

        with patch(
            "invoices.management.commands.ocr_diagnostics.shutil.which",
            return_value=None,
        ):
            call_command(
                "ocr_diagnostics",
                stdout=output,
            )

        value = output.getvalue()

        self.assertIn(
            "OCR runtime diagnostics",
            value,
        )
        self.assertIn(
            "pdfinfo: missing",
            value,
        )
        self.assertIn(
            "pdftoppm: missing",
            value,
        )
        self.assertIn(
            "tesseract: missing",
            value,
        )
        self.assertIn(
            "OCR runtime: unavailable",
            value,
        )

    def test_ocr_diagnostics_reports_available_dependencies(self):
        output = StringIO()

        def fake_which(binary_name):
            return f"/usr/bin/{binary_name}"

        with patch(
            "invoices.management.commands.ocr_diagnostics.shutil.which",
            side_effect=fake_which,
        ), patch(
            "invoices.management.commands.ocr_diagnostics.subprocess.run",
        ) as mocked_run:
            mocked_run.return_value.stdout = "fake version 1.0\n"
            mocked_run.return_value.stderr = ""

            call_command(
                "ocr_diagnostics",
                stdout=output,
            )

        value = output.getvalue()

        self.assertIn(
            "pdfinfo: ok",
            value,
        )
        self.assertIn(
            "pdftoppm: ok",
            value,
        )
        self.assertIn(
            "tesseract: ok",
            value,
        )
        self.assertIn(
            "OCR runtime: available",
            value,
        )
