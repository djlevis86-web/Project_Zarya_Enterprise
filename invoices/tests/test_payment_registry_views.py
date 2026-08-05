import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import constants as message_constants
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
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
            is_superuser=True,
        )

        self.other_staff_user = User.objects.create_user(
            username="other-staff-registry-user",
            email="other-staff-registry-user@example.com",
            password="pass12345",
            is_staff=True,
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
            full_name="Ответственный страницы реестра",
            is_active=True,
        )

    @staticmethod
    def _message_pairs(response):
        return [
            (message.level, str(message))
            for message in get_messages(response.wsgi_request)
        ]

    def _create_invoice(
        self,
        user,
        title="REGISTRY-VIEW-INVOICE-TEST",
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
            user=user,
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

    def test_unready_invoice_has_repair_action_without_selection_control(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-UNREADY-REPAIR-ACTION",
            counterparty_marker="none",
        )

        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "queue",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Контрагент не сопоставлен со справочником.",
        )

        self.assertContains(
            response,
            "Исправить",
        )

        self.assertContains(
            response,
            reverse(
                "invoice_detail",
                args=[invoice.id],
            ),
        )

        self.assertNotContains(
            response,
            f'name="invoice_ids" value="{invoice.id}"',
        )

        self.assertNotContains(
            response,
            "disabled",
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

        self.assertEqual(
            self._message_pairs(response),
            [
                (
                    message_constants.SUCCESS,
                    f"В реестр №{item.registry_id} добавлен 1 документ.",
                ),
            ],
        )

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


    def test_multiple_added_documents_use_natural_plural_success_copy(self):
        first_invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-MULTIPLE-FIRST",
        )
        second_invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-MULTIPLE-SECOND",
        )

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [
                    str(first_invoice.id),
                    str(second_invoice.id),
                ],
            },
        )

        registry = PaymentRegistry.objects.get(
            created_by=self.staff_user,
            status=PaymentRegistry.STATUS_DRAFT,
        )

        self.assertEqual(
            self._message_pairs(response),
            [
                (
                    message_constants.SUCCESS,
                    f"В реестр №{registry.id} добавлено 2 документа.",
                ),
            ],
        )

    def test_restored_document_uses_warning_tone_and_natural_copy(self):
        invoice = self._create_invoice(
            user=self.staff_user,
            title="REGISTRY-VIEW-RESTORED-WARNING",
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

        item.status = PaymentRegistryItem.STATUS_CANCELLED
        item.save(update_fields=["status"])

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [str(invoice.id)],
            },
        )

        self.assertEqual(
            self._message_pairs(response),
            [
                (
                    message_constants.SUCCESS,
                    f"В реестр №{registry.id} добавлен 1 документ.",
                ),
                (
                    message_constants.WARNING,
                    (
                        f"Документ №{invoice.id}: Ранее удалён из "
                        "черновика. Сейчас восстановлен."
                    ),
                ),
            ],
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
        self.assertEqual(
            response["Location"],
            reverse(
                "payment_registry_detail",
                args=[registry.id],
            ),
        )

        item.refresh_from_db()
        registry.refresh_from_db()

        self.assertEqual(item.status, PaymentRegistryItem.STATUS_CANCELLED)
        self.assertEqual(registry.items_count, 0)
        self.assertEqual(registry.total_amount, Decimal("0.00"))
        self.assertEqual(
            self._message_pairs(response),
            [
                (
                    message_constants.SUCCESS,
                    (
                        f"Документ №{invoice.id} удалён из реестра "
                        f"№{registry.id}. Если реестр уже выгружали, "
                        "выгрузите его повторно."
                    ),
                ),
            ],
        )

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
        self.assertEqual(
            response["Location"],
            reverse(
                "payment_registry_detail",
                args=[registry.id],
            ),
        )

        item.refresh_from_db()
        registry.refresh_from_db()

        self.assertEqual(item.status, PaymentRegistryItem.STATUS_CANCELLED)
        self.assertEqual(registry.items_count, 0)
        self.assertEqual(registry.total_amount, Decimal("0.00"))
