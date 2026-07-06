from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from invoices.models import Counterparty, Invoice
from invoices.payment_registry_services import validate_invoice_for_payment_registry


class PaymentRegistryApprovedOnlyTests(TestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.temp_dir.name
        )
        self.override.enable()

        User = get_user_model()

        self.user = User.objects.create_user(
            username="registry-approved-user",
            email="registry-approved-user@example.com",
            password="pass12345",
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО Проверенный контрагент",
            inn="3525000000",
            bank_name="Тестовый банк",
            bik="044525225",
            account_number="40702810000000000001",
        )

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()

    def create_ready_invoice(self, status):
        return Invoice.objects.create(
            user=self.user,
            title="Документ к оплате",
            amount=Decimal("1000.00"),
            amount_verified=True,
            planned_payment_date=date(2026, 7, 10),
            counterparty=self.counterparty,
            status=status,
            file=SimpleUploadedFile(
                "approved-only.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
        )

    def test_new_invoice_is_blocked_from_payment_registry(self):
        invoice = self.create_ready_invoice(
            Invoice.STATUS_NEW
        )

        errors, warnings = validate_invoice_for_payment_registry(
            invoice
        )

        self.assertIn(
            "Документ должен быть утверждён перед добавлением в реестр оплаты.",
            errors,
        )

    def test_approved_invoice_is_allowed_for_payment_registry(self):
        invoice = self.create_ready_invoice(
            Invoice.STATUS_APPROVED
        )

        errors, warnings = validate_invoice_for_payment_registry(
            invoice
        )

        self.assertEqual(
            errors,
            [],
        )

    def test_paid_invoice_is_blocked_from_payment_registry(self):
        invoice = self.create_ready_invoice(
            Invoice.STATUS_PAID
        )

        errors, warnings = validate_invoice_for_payment_registry(
            invoice
        )

        self.assertIn(
            "Документ уже находится в статусе оплаты.",
            errors,
        )

        self.assertNotIn(
            "Документ должен быть утверждён перед добавлением в реестр оплаты.",
            errors,
        )
