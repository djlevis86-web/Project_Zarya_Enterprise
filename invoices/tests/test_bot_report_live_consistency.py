from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.bot_report_services import (
    build_live_invoice_bot_report,
    get_invoice_bot_report_items,
)
from invoices.models import (
    Counterparty,
    Invoice,
    PaymentRegistry,
    PaymentRegistryItem,
    ResponsiblePerson,
)


class BotReportLiveConsistencyTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="bot-live-consistency-user",
            email="bot-live-consistency@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный live-report",
            is_active=True,
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО LIVE REPORT",
            inn="7701234567",
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810000000000001",
            bik="044525225",
            is_active=True,
        )

    def _create_ready_invoice(self, number):
        return Invoice.objects.create(
            user=self.user,
            responsible=self.responsible,
            title=f"LIVE READY {number}",
            amount=Decimal("1000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            document_date=date(2026, 7, 1),
            planned_payment_date=date(2026, 7, 20),
            vendor=self.counterparty.name,
            counterparty=self.counterparty,
            ocr_text="OCR TEXT",
        )

    def test_live_report_and_ready_category_use_same_rules(self):
        invoices = [
            self._create_ready_invoice(
                number
            )
            for number in range(5)
        ]

        registry = PaymentRegistry.objects.create(
            created_by=self.user,
            title="Активный тестовый реестр",
        )

        PaymentRegistryItem.objects.create(
            registry=registry,
            invoice=invoices[0],
            amount=invoices[0].amount,
            planned_payment_date=(
                invoices[0].planned_payment_date
            ),
        )

        with self.assertNumQueries(1):
            report = build_live_invoice_bot_report()

        with self.assertNumQueries(1):
            category_data, ready_items = (
                get_invoice_bot_report_items(
                    "ready"
                )
            )

        self.assertEqual(
            report["total_count"],
            5,
        )
        self.assertEqual(
            report["ready_for_registry_count"],
            4,
        )
        self.assertEqual(
            report["not_ready_for_registry_count"],
            1,
        )
        self.assertEqual(
            len(
                ready_items
            ),
            4,
        )

        self.assertEqual(
            category_data["title"],
            "Готовы к реестру",
        )

        ready_ids = {
            item["invoice"].id
            for item in ready_items
        }

        self.assertNotIn(
            invoices[0].id,
            ready_ids,
        )

    def test_not_ready_category_matches_live_report_count(self):
        self._create_ready_invoice(
            1
        )

        Invoice.objects.create(
            user=self.user,
            responsible=None,
            title="LIVE NOT READY",
            amount=Decimal("1000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            document_date=date(2026, 7, 1),
            planned_payment_date=date(2026, 7, 20),
            vendor=self.counterparty.name,
            counterparty=self.counterparty,
            ocr_text="OCR TEXT",
        )

        report = build_live_invoice_bot_report()

        category_data, not_ready_items = (
            get_invoice_bot_report_items(
                "not-ready"
            )
        )

        self.assertEqual(
            report["not_ready_for_registry_count"],
            len(
                not_ready_items
            ),
        )
        self.assertEqual(
            report["not_ready_for_registry_count"],
            1,
        )

        self.assertEqual(
            category_data["title"],
            "Не готовы к реестру",
        )
