from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Counterparty, Invoice


class InvoiceBotReportDetailTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="bot-report-detail-user",
            email="bot-report-detail-user@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО ДЕТАЛИЗАЦИЯ БОТА",
            full_name="Общество с ограниченной ответственностью ДЕТАЛИЗАЦИЯ БОТА",
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
            "title": "BOT DETAIL INVOICE",
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

    def test_ready_category_shows_only_ready_invoices(self):
        ready_invoice = self.create_invoice(
            title="READY DETAIL INVOICE",
        )
        not_ready_invoice = self.create_invoice(
            title="NOT READY DETAIL INVOICE",
            planned_payment_date=None,
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "ready",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "Готовы к реестру",
        )
        self.assertContains(
            response,
            ready_invoice.title,
        )
        self.assertNotContains(
            response,
            not_ready_invoice.title,
        )
        self.assertContains(
            response,
            "Нет блокировок",
        )

    def test_not_ready_category_shows_blocked_invoices(self):
        ready_invoice = self.create_invoice(
            title="READY DETAIL INVOICE",
        )
        not_ready_invoice = self.create_invoice(
            title="NO DATE DETAIL INVOICE",
            planned_payment_date=None,
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "not-ready",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "Не готовы к реестру",
        )
        self.assertContains(
            response,
            not_ready_invoice.title,
        )
        self.assertNotContains(
            response,
            ready_invoice.title,
        )
        self.assertContains(
            response,
            "Причины / проверка",
        )

    def test_without_planned_payment_date_category_filters_invoices(self):
        matching_invoice = self.create_invoice(
            title="WITHOUT DATE DETAIL INVOICE",
            planned_payment_date=None,
        )
        other_invoice = self.create_invoice(
            title="WITH DATE DETAIL INVOICE",
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "without-planned-payment-date",
                },
            )
        )

        self.assertContains(
            response,
            matching_invoice.title,
        )
        self.assertNotContains(
            response,
            other_invoice.title,
        )

    def test_without_counterparty_category_filters_invoices(self):
        matching_invoice = self.create_invoice(
            title="WITHOUT COUNTERPARTY DETAIL INVOICE",
            counterparty=None,
        )
        other_invoice = self.create_invoice(
            title="WITH COUNTERPARTY DETAIL INVOICE",
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "without-counterparty",
                },
            )
        )

        self.assertContains(
            response,
            matching_invoice.title,
        )
        self.assertNotContains(
            response,
            other_invoice.title,
        )

    def test_unverified_amount_category_filters_invoices(self):
        matching_invoice = self.create_invoice(
            title="AMOUNT NEEDS CHECK DETAIL INVOICE",
            amount_verified=False,
        )
        other_invoice = self.create_invoice(
            title="AMOUNT OK DETAIL INVOICE",
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "unverified-amount",
                },
            )
        )

        self.assertContains(
            response,
            matching_invoice.title,
        )
        self.assertNotContains(
            response,
            other_invoice.title,
        )

    def test_without_ocr_text_category_filters_invoices(self):
        matching_invoice = self.create_invoice(
            title="WITHOUT OCR DETAIL INVOICE",
            ocr_text="",
        )
        other_invoice = self.create_invoice(
            title="WITH OCR DETAIL INVOICE",
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "without-ocr-text",
                },
            )
        )

        self.assertContains(
            response,
            matching_invoice.title,
        )
        self.assertNotContains(
            response,
            other_invoice.title,
        )

    def test_unknown_category_returns_404(self):
        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "invoice_bot_report_detail",
                kwargs={
                    "category": "unknown",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )
