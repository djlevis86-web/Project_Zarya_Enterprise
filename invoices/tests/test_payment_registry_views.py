import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.models import Invoice, PaymentRegistry, PaymentRegistryItem
from invoices.payment_registry_services import (
    add_invoice_to_payment_registry,
    get_or_create_draft_payment_registry,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="zarya-test-media-")


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PaymentRegistryViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        User = get_user_model()

        self.regular_user = User.objects.create_user(
            username="regular-registry-user",
            email="regular-registry-user@example.com",
            password="pass12345",
        )

        self.staff_user = User.objects.create_user(
            username="staff-registry-user",
            email="staff-registry-user@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.other_staff_user = User.objects.create_user(
            username="other-staff-registry-user",
            email="other-staff-registry-user@example.com",
            password="pass12345",
            is_staff=True,
        )

    def _create_invoice(
        self,
        user,
        title="REGISTRY-VIEW-INVOICE-TEST",
        amount=Decimal("1000.00"),
        amount_verified=True,
    ):
        return Invoice.objects.create(
            user=user,
            title=title,
            original_filename=f"{title}.pdf",
            file=SimpleUploadedFile(
                f"{title}.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            amount=amount,
            status=Invoice.STATUS_APPROVED,
            amount_verified=amount_verified,
        )

    def test_add_to_payment_registry_requires_login(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-LOGIN-REQUIRED",
        )

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [str(invoice.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertFalse(
            PaymentRegistryItem.objects.filter(invoice=invoice).exists()
        )

    def test_regular_user_without_permission_cannot_add_invoice(self):
        invoice = self._create_invoice(
            user=self.regular_user,
            title="REGISTRY-VIEW-NO-PERMISSION",
        )

        self.client.force_login(self.regular_user)

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [str(invoice.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payment_registry"), response["Location"])
        self.assertFalse(
            PaymentRegistryItem.objects.filter(invoice=invoice).exists()
        )

    def test_get_request_does_not_add_invoice_to_registry(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-GET-NOT-ALLOWED",
        )

        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("add_to_payment_registry"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payment_schedule"), response["Location"])
        self.assertFalse(
            PaymentRegistryItem.objects.filter(invoice=invoice).exists()
        )

    def test_staff_can_add_verified_invoice_to_registry(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-STAFF-ADD",
            amount=Decimal("1000.00"),
            amount_verified=True,
        )

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [str(invoice.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payment_registry"), response["Location"])

        item = PaymentRegistryItem.objects.get(invoice=invoice)

        self.assertEqual(item.status, PaymentRegistryItem.STATUS_ADDED)
        self.assertEqual(item.amount, Decimal("1000.00"))
        self.assertEqual(item.registry.created_by, self.staff_user)
        self.assertEqual(item.registry.status, PaymentRegistry.STATUS_DRAFT)

        item.registry.refresh_from_db()

        self.assertEqual(item.registry.items_count, 1)
        self.assertEqual(item.registry.total_amount, Decimal("1000.00"))

    def test_staff_cannot_add_unverified_invoice_to_registry(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-UNVERIFIED",
            amount=Decimal("1000.00"),
            amount_verified=False,
        )

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [str(invoice.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payment_registry"), response["Location"])
        self.assertFalse(
            PaymentRegistryItem.objects.filter(invoice=invoice).exists()
        )
        self.assertFalse(
            PaymentRegistry.objects.filter(created_by=self.staff_user).exists()
        )

    def test_staff_can_remove_item_from_own_draft_registry(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-REMOVE-OWN",
            amount=Decimal("1000.00"),
            amount_verified=True,
        )
        registry, _ = get_or_create_draft_payment_registry(self.staff_user)
        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(item)
        self.assertEqual(errors, [])

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("remove_from_payment_registry_item", args=[item.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payment_registry"), response["Location"])

        item.refresh_from_db()
        registry.refresh_from_db()

        self.assertEqual(item.status, PaymentRegistryItem.STATUS_CANCELLED)
        self.assertEqual(registry.items_count, 0)
        self.assertEqual(registry.total_amount, Decimal("0.00"))

    def test_staff_can_remove_item_from_foreign_draft_registry(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-REMOVE-FOREIGN",
            amount=Decimal("1000.00"),
            amount_verified=True,
        )

        registry, _ = get_or_create_draft_payment_registry(
            self.staff_user
        )

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(item)
        self.assertEqual(errors, [])

        self.client.force_login(
            self.other_staff_user
        )

        response = self.client.post(
            reverse("remove_from_payment_registry_item", args=[item.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payment_registry"), response["Location"])

        item.refresh_from_db()
        registry.refresh_from_db()

        self.assertEqual(item.status, PaymentRegistryItem.STATUS_CANCELLED)
        self.assertEqual(registry.items_count, 0)
        self.assertEqual(registry.total_amount, Decimal("0.00"))
