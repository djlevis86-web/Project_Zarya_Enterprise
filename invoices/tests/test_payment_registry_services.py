import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from invoices.models import (
    Counterparty,
    Invoice,
    PaymentRegistry,
    PaymentRegistryItem,
    ResponsiblePerson,
)
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

        self.counterparty = Counterparty.objects.create(
            name="ТЕСТОВЫЙ ПОСТАВЩИК",
            full_name="ООО ТЕСТОВЫЙ ПОСТАВЩИК",
            inn="7705551111",
            kpp="770501001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810900000000001",
            bik="044525225",
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный реестра",
            is_active=True,
        )

    def _create_invoice(
        self,
        title="REGISTRY-INVOICE-TEST",
        amount=Decimal("1000.00"),
        amount_verified=True,
        planned_payment_date=None,
        counterparty_marker="default",
    ):
        if planned_payment_date is None:
            planned_payment_date = timezone.localdate()

        counterparty = self.counterparty

        if counterparty_marker == "none":
            counterparty = None

        return Invoice.objects.create(
            user=self.user,
            responsible=self.responsible,
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
            planned_payment_date=planned_payment_date,
            counterparty=counterparty,
            vendor=getattr(counterparty, "name", "") if counterparty else "",
            counterparty_match_status=Invoice.COUNTERPARTY_MATCH_FOUND if counterparty else Invoice.COUNTERPARTY_MATCH_NOT_FOUND,
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
            "Сумма документа не подтверждена после OCR-проверки.",
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

    def test_invoice_without_planned_payment_date_is_not_added(self):
        invoice = self._create_invoice(
            title="REGISTRY-NO-PLAN-DATE",
        )

        invoice.planned_payment_date = None
        invoice.save(update_fields=["planned_payment_date"])

        registry, _ = get_or_create_draft_payment_registry(self.user)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNone(item)
        self.assertIn(
            "Не указана плановая дата оплаты.",
            errors,
        )
        self.assertFalse(
            PaymentRegistryItem.objects.filter(
                registry=registry,
                invoice=invoice,
            ).exists()
        )

    def test_invoice_without_responsible_is_not_added(self):
        invoice = self._create_invoice(
            title="REGISTRY-NO-RESPONSIBLE",
        )

        invoice.responsible = None
        invoice.save(
            update_fields=[
                "responsible",
            ]
        )

        registry, _ = get_or_create_draft_payment_registry(
            self.user
        )

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNone(item)
        self.assertIn(
            "Ответственный не назначен.",
            errors,
        )
        self.assertFalse(
            PaymentRegistryItem.objects.filter(
                registry=registry,
                invoice=invoice,
            ).exists()
        )

    def test_invoice_without_counterparty_is_not_added(self):
        invoice = self._create_invoice(
            title="REGISTRY-NO-COUNTERPARTY",
            counterparty_marker="none",
        )

        registry, _ = get_or_create_draft_payment_registry(self.user)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNone(item)
        self.assertIn(
            "Контрагент не сопоставлен со справочником.",
            errors,
        )

    def test_invoice_with_counterparty_missing_requisites_is_not_added(self):
        self.counterparty.account_number = ""
        self.counterparty.bik = ""
        self.counterparty.save(
            update_fields=[
                "account_number",
                "bik",
            ]
        )

        invoice = self._create_invoice(
            title="REGISTRY-MISSING-REQUISITES",
        )

        registry, _ = get_or_create_draft_payment_registry(self.user)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNone(item)
        self.assertIn(
            "У контрагента не заполнено: расчётный счёт, БИК.",
            errors,
        )

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
            f"Документ уже есть в реестре №{registry.id}.",
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
            "Документ был ранее удалён из черновика и теперь восстановлен.",
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