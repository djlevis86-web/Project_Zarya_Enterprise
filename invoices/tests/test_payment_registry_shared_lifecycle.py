import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from invoices.models import Counterparty
from invoices.models import Invoice
from invoices.models import PaymentRegistry
from invoices.models import PaymentRegistryItem
from invoices.payment_registry_services import (
    add_invoice_to_payment_registry,
    get_or_create_draft_payment_registry,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-test-media-registry-shared-lifecycle-"
)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PaymentRegistrySharedLifecycleTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(
            _TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self):
        User = get_user_model()

        self.first_user = User.objects.create_user(
            username="registry-shared-first",
            email="registry-shared-first@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )

        self.second_user = User.objects.create_user(
            username="registry-shared-second",
            email="registry-shared-second@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
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

    def _create_invoice(self, user, title="REGISTRY-SHARED-INVOICE"):
        return Invoice.objects.create(
            user=user,
            title=title,
            original_filename=f"{title}.pdf",
            file=SimpleUploadedFile(
                f"{title}.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            amount=Decimal("1000.00"),
            status=Invoice.STATUS_APPROVED,
            amount_verified=True,
            planned_payment_date=timezone.localdate(),
            counterparty=self.counterparty,
            vendor=self.counterparty.name,
            counterparty_match_status=Invoice.COUNTERPARTY_MATCH_FOUND,
        )

    def test_get_or_create_reuses_foreign_editable_registry(self):
        first_registry, first_created = get_or_create_draft_payment_registry(
            self.first_user
        )

        second_registry, second_created = get_or_create_draft_payment_registry(
            self.second_user
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_registry.id, second_registry.id)
        self.assertEqual(first_registry.created_by, self.first_user)

    def test_payment_registry_page_does_not_create_empty_draft(self):
        self.client.force_login(
            self.first_user
        )

        response = self.client.get(
            reverse("payment_registry")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            PaymentRegistry.objects.exists()
        )

    def test_second_staff_user_sees_shared_draft_registry(self):
        invoice = self._create_invoice(
            self.first_user,
            "REGISTRY-SHARED-VISIBLE",
        )

        registry, created = get_or_create_draft_payment_registry(
            self.first_user
        )

        self.assertTrue(created)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(item)
        self.assertEqual(errors, [])

        self.client.force_login(
            self.second_user
        )

        response = self.client.get(
            reverse("payment_registry")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["draft_registry"].id,
            registry.id,
        )

        self.assertEqual(
            list(response.context["draft_registry_items"]),
            [item],
        )

    def test_second_staff_user_can_export_shared_registry_excel(self):
        invoice = self._create_invoice(
            self.first_user,
            "REGISTRY-SHARED-EXCEL",
        )

        registry, created = get_or_create_draft_payment_registry(
            self.first_user
        )

        self.assertTrue(created)

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(item)
        self.assertEqual(errors, [])

        self.client.force_login(
            self.second_user
        )

        response = self.client.post(
            reverse(
                "export_payment_registry_draft_excel",
                args=[registry.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
            (
                f"redirect={response.get('Location')} "
                f"messages={[str(message) for message in get_messages(response.wsgi_request)]}"
            ),
        )

        self.assertIn(
            "spreadsheetml.sheet",
            response["Content-Type"],
        )
