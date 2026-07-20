import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import (
    Counterparty,
    Invoice,
    ResponsiblePerson,
)


class DashboardInvoiceBotReportTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="dashboard-bot-user",
            email="dashboard-bot-user@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный Dashboard",
            is_active=True,
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО DASHBOARD TEST",
            inn="7701234567",
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810000000000001",
            bik="044525225",
            is_active=True,
        )

    def _create_invoice(self, **kwargs):
        defaults = {
            "user": self.user,
            "title": "DASHBOARD LIVE INVOICE",
            "amount": Decimal("1000.00"),
            "amount_verified": True,
            "status": Invoice.STATUS_APPROVED,
            "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            "document_date": date(2026, 7, 1),
            "planned_payment_date": date(2026, 7, 20),
            "responsible": self.responsible,
            "vendor": self.counterparty.name,
            "counterparty": self.counterparty,
            "ocr_text": "OCR TEXT",
        }

        defaults.update(
            kwargs
        )

        return Invoice.objects.create(
            **defaults
        )

    def _write_stale_report(self, base_dir):
        report_path = (
            base_dir
            / "var"
            / "invoice_bot"
            / "latest_report.json"
        )

        report_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        report_path.write_text(
            json.dumps(
                {
                    "report_version": 2,
                    "generated_at": (
                        "2026-07-03T22:17:29.001994+00:00"
                    ),
                    "total_count": 201,
                    "without_planned_payment_date_count": 146,
                    "without_counterparty_count": 12,
                    "unverified_amount_count": 121,
                    "without_ocr_text_count": 8,
                    "unknown_document_type_count": 3,
                    "ready_for_registry_count": 12,
                    "not_ready_for_registry_count": 189,
                    "without_vendor_count": 4,
                    "counterparty_action_required_count": 2,
                    "waiting_1c_sync_count": 10,
                    "mode": "audit_only",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_dashboard_has_single_accessible_primary_heading(self):
        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            (
                '<h1 id="dashboard-title" '
                'class="dashboard-title">'
                "Управление документами к оплате и оплатами"
                "</h1>"
            ),
            html=True,
        )

        self.assertNotContains(
            response,
            '<div class="page-header">',
        )

        response_html = response.content.decode(
            "utf-8"
        )

        self.assertEqual(
            response_html.count(
                "<h1"
            ),
            1,
        )

    def test_dashboard_counts_in_work_documents(self):
        self._create_invoice(
            title="IN WORK DASHBOARD INVOICE",
            status=Invoice.STATUS_IN_WORK,
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context[
                "review_count"
            ],
            1,
        )

        attention_items = response.context[
            "attention_items"
        ]

        review_item = next(
            item
            for item in attention_items
            if item["label"] == "На проверке"
        )

        self.assertEqual(
            review_item["value"],
            1,
        )

    def test_dashboard_prioritizes_user_work_before_technical_audit(self):
        self._create_invoice()

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        response_html = response.content.decode(
            "utf-8"
        )

        attention_position = response_html.index(
            'class="dashboard-attention-v1"'
        )

        bot_report_position = response_html.index(
            'class="card dashboard-bot-report-v2"'
        )

        user_queue_position = response_html.index(
            "Рабочая очередь пользователя"
        )

        technical_audit_position = response_html.index(
            "Технический аудит"
        )

        self.assertLess(
            attention_position,
            bot_report_position,
        )

        self.assertLess(
            user_queue_position,
            technical_audit_position,
        )

        self.assertEqual(
            response_html.count(
                'class="dashboard-attention-v1"'
            ),
            1,
        )

    def test_dashboard_uses_live_counts_instead_of_stale_json(self):
        self._create_invoice(
            title="READY DASHBOARD INVOICE",
        )

        self._create_invoice(
            title="NO DATE DASHBOARD INVOICE",
            planned_payment_date=None,
        )

        with TemporaryDirectory() as temp_dir:
            base_dir = Path(
                temp_dir
            )

            self._write_stale_report(
                base_dir
            )

            self.client.force_login(
                self.user
            )

            with self.settings(
                BASE_DIR=base_dir
            ):
                response = self.client.get(
                    reverse(
                        "dashboard"
                    )
                )

        self.assertEqual(
            response.status_code,
            200,
        )

        report = response.context[
            "invoice_bot_report"
        ]

        self.assertEqual(
            report["total_count"],
            2,
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
            report["without_planned_payment_date_count"],
            1,
        )

        self.assertNotEqual(
            report["ready_for_registry_count"],
            12,
        )

        self.assertContains(
            response,
            "Актуальное состояние документов",
        )
        self.assertContains(
            response,
            "последний автоматический аудит",
        )

    def test_dashboard_works_without_invoice_bot_report_json(self):
        self._create_invoice()

        with TemporaryDirectory() as temp_dir:
            base_dir = Path(
                temp_dir
            )

            self.client.force_login(
                self.user
            )

            with self.settings(
                BASE_DIR=base_dir
            ):
                response = self.client.get(
                    reverse(
                        "dashboard"
                    )
                )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertNotContains(
            response,
            "Отчёт бота",
        )

    def test_dashboard_invoice_bot_report_cards_link_to_detail_pages(self):
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(
                temp_dir
            )

            self._write_stale_report(
                base_dir
            )

            self.client.force_login(
                self.user
            )

            with self.settings(
                BASE_DIR=base_dir
            ):
                response = self.client.get(
                    reverse(
                        "dashboard"
                    )
                )

        categories = (
            "ready",
            "not-ready",
            "without-planned-payment-date",
            "without-counterparty",
            "unverified-amount",
            "without-ocr-text",
            "unknown-document-type",
        )

        for category in categories:
            self.assertContains(
                response,
                reverse(
                    "invoice_bot_report_detail",
                    kwargs={
                        "category": category,
                    },
                ),
            )
