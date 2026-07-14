import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DashboardInvoiceBotReportTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="dashboard-bot-user",
            email="dashboard-bot-user@example.com",
            password="pass12345",
            is_staff=True,
        )

    def _write_report(self, base_dir):
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
                    "generated_at": "2026-07-03T22:17:29.001994+00:00",
                    "total_count": 201,
                    "without_planned_payment_date_count": 146,
                    "without_counterparty_count": 12,
                    "unverified_amount_count": 121,
                    "without_ocr_text_count": 8,
                    "unknown_document_type_count": 3,
                    "ready_for_registry_count": 36,
                    "not_ready_for_registry_count": 165,
                    "without_vendor_count": 4,
                    "counterparty_action_required_count": 2,
                    "waiting_1c_sync_count": 10,
                    "mode": "audit_only",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_dashboard_shows_invoice_bot_report_when_json_exists(self):
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(
                temp_dir
            )

            self._write_report(
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
        self.assertContains(
            response,
            "Отчёт бота",
        )
        self.assertContains(
            response,
            "Активных документов",
        )
        self.assertContains(
            response,
            "201",
        )

        self.assertContains(
            response,
            "Технический аудит",
        )
        self.assertContains(
            response,
            "Без OCR-текста",
        )
        self.assertContains(
            response,
            "8",
        )
        self.assertContains(
            response,
            "Неизвестный тип",
        )
        self.assertContains(
            response,
            "3",
        )
        self.assertContains(
            response,
            "Без заполненного поставщика",
        )
        self.assertContains(
            response,
            "4",
        )
        self.assertContains(
            response,
            "Без контрагента",
        )
        self.assertContains(
            response,
            "12",
        )
        self.assertContains(
            response,
            "Требуют проверки контрагента",
        )
        self.assertContains(
            response,
            "2",
        )
        self.assertContains(
            response,
            "Ожидают синхронизацию 1С",
        )
        self.assertContains(
            response,
            "10",
        )

        self.assertContains(
            response,
            "Рабочая очередь пользователя",
        )
        self.assertContains(
            response,
            "Готовы к реестру",
        )
        self.assertContains(
            response,
            "36",
        )
        self.assertContains(
            response,
            "Не готовы",
        )
        self.assertContains(
            response,
            "165",
        )
        self.assertContains(
            response,
            "Без даты оплаты",
        )
        self.assertContains(
            response,
            "146",
        )
        self.assertContains(
            response,
            "Сумма ожидает подтверждения",
        )
        self.assertContains(
            response,
            "121",
        )

    def test_dashboard_works_without_invoice_bot_report_json(self):
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

            self._write_report(
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

        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "ready",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "not-ready",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "without-planned-payment-date",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "without-counterparty",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "unverified-amount",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "without-ocr-text",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "unknown-document-type",
                },
            ),
        )
