import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from invoices.models import Counterparty, Invoice


class InvoiceBotRunnerTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="invoice-bot-user",
            email="invoice-bot-user@example.com",
            password="pass12345",
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО БОТ ТЕСТ",
            full_name="Общество с ограниченной ответственностью БОТ ТЕСТ",
            inn="7701234567",
            kpp="770101001",
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810000000000001",
            bik="044525225",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

    def create_invoice(self, **kwargs):
        defaults = {
            "user": self.user,
            "title": "BOT TEST INVOICE",
            "amount": Decimal("1000.00"),
            "amount_verified": True,
            "status": Invoice.STATUS_APPROVED,
            "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            "document_date": date(2026, 7, 1),
            "planned_payment_date": date(2026, 7, 10),
            "counterparty": self.counterparty,
            "ocr_text": "OCR TEXT",
        }
        defaults.update(
            kwargs
        )

        return Invoice.objects.create(
            **defaults
        )

    def test_run_invoice_bot_prints_safe_audit_report(self):
        self.create_invoice(
            title="READY BOT INVOICE",
        )

        self.create_invoice(
            title="NO DATE BOT INVOICE",
            planned_payment_date=None,
        )

        self.create_invoice(
            title="NO COUNTERPARTY BOT INVOICE",
            counterparty=None,
        )

        self.create_invoice(
            title="UNVERIFIED NO OCR BOT INVOICE",
            amount_verified=False,
            ocr_text="",
        )

        self.create_invoice(
            title="DELETED BOT INVOICE",
            is_deleted=True,
            planned_payment_date=None,
            counterparty=None,
            amount_verified=False,
            ocr_text="",
        )

        out = StringIO()

        call_command(
            "run_invoice_bot",
            stdout=out,
        )

        output = out.getvalue()

        self.assertIn(
            "Invoice Bot Report",
            output,
        )
        self.assertIn(
            "Всего активных счетов: 4",
            output,
        )
        self.assertIn(
            "Без плановой даты оплаты: 1",
            output,
        )
        self.assertIn(
            "Без контрагента: 1",
            output,
        )
        self.assertIn(
            "С неподтверждённой суммой: 1",
            output,
        )
        self.assertIn(
            "Без OCR-текста: 1",
            output,
        )
        self.assertIn(
            "Готовы к реестру оплаты: 1",
            output,
        )
        self.assertIn(
            "Не готовы к реестру оплаты: 3",
            output,
        )
        self.assertIn(
            "Режим: только аудит, без изменения данных",
            output,
        )

    def test_run_invoice_bot_writes_json_report(self):
        self.create_invoice(
            title="READY JSON BOT INVOICE",
        )

        self.create_invoice(
            title="NO DATE JSON BOT INVOICE",
            planned_payment_date=None,
        )

        with TemporaryDirectory() as temp_dir:
            report_path = (
                Path(temp_dir)
                / "invoice_bot"
                / "latest_report.json"
            )

            out = StringIO()

            call_command(
                "run_invoice_bot",
                "--json",
                f"--json-path={report_path}",
                stdout=out,
            )

            self.assertTrue(
                report_path.exists()
            )

            report = json.loads(
                report_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "generated_at",
                report,
            )
            self.assertEqual(
                report["total_count"],
                2,
            )
            self.assertEqual(
                report["without_planned_payment_date_count"],
                1,
            )
            self.assertEqual(
                report["without_counterparty_count"],
                0,
            )
            self.assertEqual(
                report["unverified_amount_count"],
                0,
            )
            self.assertEqual(
                report["without_ocr_text_count"],
                0,
            )
            self.assertEqual(
                report["ready_for_registry_count"],
                1,
            )
            self.assertEqual(
                report["not_ready_for_registry_count"],
                1,
            )
            self.assertEqual(
                report["mode"],
                "audit_only",
            )
            self.assertIn(
                "JSON-отчёт сохранён",
                out.getvalue(),
            )
