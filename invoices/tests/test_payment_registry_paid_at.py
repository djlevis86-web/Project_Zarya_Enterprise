from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.models import (
    Counterparty,
    Invoice,
    InvoicePayment,
    PaymentRegistry,
    PaymentRegistryItem,
)
from invoices.payment_registry_services import mark_payment_registry_as_paid


class PaymentRegistryPaidAtTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="registry-paid-at-user",
            email="registry-paid-at-user@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО Реестр Оплата",
            full_name="Общество с ограниченной ответственностью Реестр Оплата",
            inn="7701234567",
            kpp="770101001",
            bank_name="Тестовый банк",
            bik="044525225",
            account_number="40702810900000000001",
            correspondent_account="30101810400000000225",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            counterparty=self.counterparty,
            title="Registry paid at invoice",
            amount=Decimal("1000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
            planned_payment_date=timezone.localdate(),
        )

        self.registry = PaymentRegistry.objects.create(
            created_by=self.user,
            title="Registry paid at test",
            status=PaymentRegistry.STATUS_EXPORTED,
            items_count=1,
            total_amount=Decimal("1000.00"),
        )

        self.item = PaymentRegistryItem.objects.create(
            registry=self.registry,
            invoice=self.invoice,
            amount=Decimal("1000.00"),
            planned_payment_date=timezone.localdate(),
            status=PaymentRegistryItem.STATUS_EXPORTED,
        )

    def test_mark_payment_registry_as_paid_sets_registry_paid_at(self):
        self.assertIsNone(
            self.registry.paid_at
        )

        mark_payment_registry_as_paid(
            self.registry,
            user=self.user,
        )

        self.registry.refresh_from_db()
        self.item.refresh_from_db()
        self.invoice.refresh_from_db()

        self.assertEqual(
            self.registry.status,
            PaymentRegistry.STATUS_PAID,
        )
        self.assertIsNotNone(
            self.registry.paid_at,
        )
        self.assertEqual(
            self.item.status,
            PaymentRegistryItem.STATUS_PAID,
        )
        self.assertIsNotNone(
            self.item.paid_at,
        )
        self.assertEqual(
            self.invoice.status,
            Invoice.STATUS_APPROVED,
        )
        self.assertEqual(
            self.invoice.payment_status_code,
            "paid",
        )
        self.assertTrue(
            InvoicePayment.objects.filter(
                invoice=self.invoice,
                registry_item=self.item,
                status=InvoicePayment.STATUS_POSTED,
                amount=Decimal("1000.00"),
            ).exists()
        )

    def test_payment_registry_history_shows_registry_paid_at(self):
        paid_at = timezone.make_aware(
            datetime(
                2026,
                7,
                3,
                14,
                30,
                0,
            )
        )

        self.registry.status = PaymentRegistry.STATUS_PAID
        self.registry.paid_at = paid_at
        self.registry.save(
            update_fields=[
                "status",
                "paid_at",
            ]
        )

        expected_paid_at = timezone.localtime(
            paid_at
        ).strftime(
            "%d.%m.%Y %H:%M"
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("payment_registry_history")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "Факт. оплата",
        )
        self.assertContains(
            response,
            expected_paid_at,
        )

