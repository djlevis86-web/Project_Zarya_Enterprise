from pathlib import Path

from django.test import SimpleTestCase


class InvoiceUploadCounterpartyMatchTests(SimpleTestCase):
    def test_upload_flow_runs_counterparty_matching_after_ocr(self):
        source = Path(
            "invoices/view_modules/invoice_upload_views.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "get_or_create_counterparty_from_invoice",
            source,
        )
        self.assertIn(
            "def match_counterparty_after_upload_ocr(",
            source,
        )
        self.assertIn(
            "match_counterparty_after_upload_ocr(\n                    invoice,\n                    request.user,\n                )",
            source,
        )
