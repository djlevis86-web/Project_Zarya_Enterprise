from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class ProcessOCRQueueCommandTests(TestCase):
    def test_process_ocr_queue_command_runs_without_pending_jobs(self):
        output = StringIO()

        call_command(
            "process_ocr_queue",
            limit=1,
            stdout=output,
        )

        self.assertIn(
            "Нет задач OCR в очереди.",
            output.getvalue(),
        )