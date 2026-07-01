import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from invoices.models import Invoice, PaymentRegistry, PaymentRegistryItem
from invoices.payment_registry_services import (
    add_invoice_to_payment_registry,
    get_or_create_draft_payment_registry,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="zarya-test-media-")


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PaymentRegistryServiceTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="registry-user",
            email="registry-user@example.com",
            password="pass12345",
        )

    def _create_invoice(
        self,
        title="REGISTRY-INVOICE-TEST",
        amount=Decimal("1000.00"),
        amount_verified=True,
    ):
        return Invoice.objects.create(
            user=self.user,
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

    def test_get_or_create_draft_payment_registry_creates_registry(self):
        registry, created = get_or_create_draft_payment_registry(self.user)

        self.assertTrue(created)
        self.assertEqual(registry.created_by, self.user)
        self.assertEqual(registry.status, PaymentRegistry.STATUS_DRAFT)
        self.assertEqual(registry.items_count, 0)
        self.assertEqual(registry.total_amount, Decimal("0"))

    def test_get_or_create_draft_payment_registry_reuses_existing_draft(self):
        first_registry, first_created = get_or_create_draft_payment_registry(
            self.user
        )
        second_registry, second_created = get_or_create_draft_payment_registry(
            self.user
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_registry.id, second_registry.id)

    def test_add_verified_invoice_to_payment_registry(self):
        invoice = self._create_invoice(
            title="REGISTRY-VERIFIED-INVOICE",
            amount=Decimal("1000.00"),
            amount_verified=True,
        )
        registry, _ = get_or_create_draft_payment_registry(self.user)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(item)
        self.assertEqual(errors, [])
        self.assertEqual(item.invoice, invoice)
        self.assertEqual(item.registry, registry)
        self.assertEqual(item.amount, Decimal("1000.00"))
        self.assertEqual(item.status, PaymentRegistryItem.STATUS_ADDED)

        registry.refresh_from_db()

        self.assertEqual(registry.items_count, 1)
        self.assertEqual(registry.total_amount, Decimal("1000.00"))

    def test_unverified_invoice_is_not_added_to_payment_registry(self):
        invoice = self._create_invoice(
            title="REGISTRY-UNVERIFIED-INVOICE",
            amount=Decimal("1000.00"),
            amount_verified=False,
        )
        registry, _ = get_or_create_draft_payment_registry(self.user)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNone(item)
        self.assertTrue(errors)
        self.assertIn(
            "Сумма счёта не подтверждена после OCR-проверки.",
            errors,
        )
        self.assertFalse(
            PaymentRegistryItem.objects.filter(
                registry=registry,
                invoice=invoice,
            ).exists()
        )

        registry.refresh_from_db()

        self.assertEqual(registry.items_count, 0)
        self.assertEqual(registry.total_amount, Decimal("0.00"))

    def test_duplicate_active_invoice_is_not_added_twice(self):
        invoice = self._create_invoice(
            title="REGISTRY-DUPLICATE-INVOICE",
            amount=Decimal("1000.00"),
            amount_verified=True,
        )
        registry, _ = get_or_create_draft_payment_registry(self.user)

        first_item, first_errors, first_warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )
        second_item, second_errors, second_warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(first_item)
        self.assertEqual(first_errors, [])

        self.assertIsNone(second_item)
        self.assertTrue(second_errors)
        self.assertIn(
            f"Счёт уже есть в реестре №{registry.id}.",
            second_errors,
        )

        self.assertEqual(
            PaymentRegistryItem.objects.filter(
                registry=registry,
                invoice=invoice,
            ).count(),
            1,
        )

        registry.refresh_from_db()

        self.assertEqual(registry.items_count, 1)
        self.assertEqual(registry.total_amount, Decimal("1000.00"))

    def test_cancelled_registry_item_is_restored(self):
        invoice = self._create_invoice(
            title="REGISTRY-RESTORE-INVOICE",
            amount=Decimal("1000.00"),
            amount_verified=True,
        )
        registry, _ = get_or_create_draft_payment_registry(self.user)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(item)
        self.assertEqual(errors, [])

        item.status = PaymentRegistryItem.STATUS_CANCELLED
        item.save(update_fields=["status"])

        restored_item, restore_errors, restore_warnings = (
            add_invoice_to_payment_registry(
                invoice,
                registry,
            )
        )

        self.assertEqual(restore_errors, [])
        self.assertIsNotNone(restored_item)
        self.assertEqual(restored_item.id, item.id)
        self.assertEqual(restored_item.status, PaymentRegistryItem.STATUS_ADDED)
        self.assertIn(
            "Счёт был ранее удалён из черновика и теперь восстановлен.",
            restore_warnings,
        )

        self.assertEqual(
            PaymentRegistryItem.objects.filter(
                registry=registry,
                invoice=invoice,
            ).count(),
            1,
        )

        registry.refresh_from_db()

        self.assertEqual(registry.items_count, 1)
        self.assertEqual(registry.total_amount, Decimal("1000.00"))