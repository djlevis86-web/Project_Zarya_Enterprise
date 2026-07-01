from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice, PaymentRegistry, PaymentRegistryItem
from invoices.payment_registry_services import (
    get_or_create_draft_payment_registry,
    payment_registry_can_be_edited,
)


class PaymentRegistryEditingRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="registry-editor",
            email="registry-editor@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            title="Editable exported registry invoice",
            amount=Decimal("1000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
        )

    def _registry_with_item(self, status):
        registry = PaymentRegistry.objects.create(
            created_by=self.user,
            title="Test payment registry",
            status=status,
            items_count=1,
            total_amount=Decimal("1000.00"),
        )

        item = PaymentRegistryItem.objects.create(
            registry=registry,
            invoice=self.invoice,
            amount=Decimal("1000.00"),
            status=PaymentRegistryItem.STATUS_EXPORTED
            if status == PaymentRegistry.STATUS_EXPORTED
            else PaymentRegistryItem.STATUS_ADDED,
        )

        return registry, item

    def test_exported_registry_is_editable(self):
        registry, _ = self._registry_with_item(PaymentRegistry.STATUS_EXPORTED)

        self.assertTrue(payment_registry_can_be_edited(registry))

    def test_paid_registry_is_not_editable(self):
        registry, _ = self._registry_with_item(PaymentRegistry.STATUS_PAID)

        self.assertFalse(payment_registry_can_be_edited(registry))

    def test_get_or_create_reuses_exported_registry_until_paid(self):
        registry, _ = self._registry_with_item(PaymentRegistry.STATUS_EXPORTED)

        found_registry, created = get_or_create_draft_payment_registry(self.user)

        self.assertFalse(created)
        self.assertEqual(found_registry.id, registry.id)

    def test_can_remove_item_from_exported_registry_and_registry_becomes_draft(self):
        registry, item = self._registry_with_item(PaymentRegistry.STATUS_EXPORTED)

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("remove_from_payment_registry_item", args=[item.id])
        )

        self.assertEqual(response.status_code, 302)

        item.refresh_from_db()
        registry.refresh_from_db()

        self.assertEqual(item.status, PaymentRegistryItem.STATUS_CANCELLED)
        self.assertEqual(registry.status, PaymentRegistry.STATUS_DRAFT)

    def test_cannot_remove_item_from_paid_registry(self):
        registry, item = self._registry_with_item(PaymentRegistry.STATUS_PAID)

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("remove_from_payment_registry_item", args=[item.id])
        )

        self.assertEqual(response.status_code, 302)

        item.refresh_from_db()
        registry.refresh_from_db()

        self.assertNotEqual(item.status, PaymentRegistryItem.STATUS_CANCELLED)
        self.assertEqual(registry.status, PaymentRegistry.STATUS_PAID)
