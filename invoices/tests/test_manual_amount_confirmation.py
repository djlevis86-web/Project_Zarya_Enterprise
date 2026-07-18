import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from invoices.models import (
    Counterparty,
    Invoice,
    PaymentRegistryItem,
    ResponsiblePerson,
)
from invoices.ocr_verification_service import (
    apply_ocr_amount_to_invoice,
)
from invoices.payment_registry_services import (
    add_invoice_to_payment_registry,
    get_or_create_draft_payment_registry,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-test-manual-amount-confirmation-"
)


@override_settings(
    MEDIA_ROOT=_TEST_MEDIA_ROOT
)
class ManualAmountConfirmationTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        shutil.rmtree(
            _TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self):
        User = get_user_model()

        self.staff_user = User.objects.create_user(
            username="manual-amount-staff",
            email="manual-amount-staff@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный по ручной сумме",
            is_active=True,
        )

        self.counterparty = Counterparty.objects.create(
            name="РУЧНАЯ СУММА ПОСТАВЩИК",
            full_name="ООО РУЧНАЯ СУММА ПОСТАВЩИК",
            inn="7705552222",
            kpp="770501001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
            bank_name="АО РУЧНОЙ БАНК",
            account_number="40702810900000000002",
            bik="044525226",
        )

    def _create_invoice(
        self,
        *,
        amount=Decimal("120000.00"),
        ocr_amount=Decimal("120000.00"),
        amount_verified=False,
        ocr_verified=False,
    ):
        return Invoice.objects.create(
            user=self.staff_user,
            responsible=self.responsible,
            counterparty=self.counterparty,
            counterparty_match_status=(
                Invoice.COUNTERPARTY_MATCH_FOUND
            ),
            title="MANUAL AMOUNT INVOICE",
            original_filename="manual-amount.pdf",
            file=SimpleUploadedFile(
                "manual-amount.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            vendor=self.counterparty.name,
            amount=amount,
            ocr_amount=ocr_amount,
            amount_verified=amount_verified,
            ocr_verified=ocr_verified,
            planned_payment_date=timezone.localdate(),
            payment_priority=3,
            status=Invoice.STATUS_APPROVED,
        )

    def _edit_payload(
        self,
        invoice,
        *,
        amount,
        title=None,
    ):
        return {
            "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            "title": title or invoice.title,
            "description": invoice.description or "",
            "vendor": invoice.vendor or "",
            "invoice_number": invoice.invoice_number or "",
            "invoice_date": "",
            "document_date": "",
            "amount": str(amount),
            "planned_payment_date": (
                invoice.planned_payment_date.isoformat()
            ),
            "responsible": str(
                self.responsible.id
            ),
            "payment_priority": str(
                invoice.payment_priority
            ),
            "paid_at": "",
            "status": Invoice.STATUS_APPROVED,
        }

    def test_manual_corrected_amount_is_allowed_in_payment_registry(self):
        invoice = self._create_invoice()

        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            ),
            self._edit_payload(
                invoice,
                amount="125000.00",
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.amount,
            Decimal("125000.00"),
        )
        self.assertTrue(
            invoice.amount_verified
        )
        self.assertFalse(
            invoice.ocr_verified
        )
        self.assertIn(
            "Приоритет имеет сумма, проверенная пользователем",
            invoice.ocr_comment,
        )

        registry, _ = get_or_create_draft_payment_registry(
            self.staff_user
        )

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry,
        )

        self.assertIsNotNone(
            item
        )
        self.assertEqual(
            errors,
            [],
        )
        self.assertEqual(
            warnings,
            [],
        )
        self.assertEqual(
            item.amount,
            Decimal("125000.00"),
        )
        self.assertTrue(
            PaymentRegistryItem.objects.filter(
                registry=registry,
                invoice=invoice,
            ).exists()
        )

    def test_editing_other_fields_does_not_confirm_unchanged_amount(self):
        invoice = self._create_invoice(
            amount_verified=False,
            ocr_verified=False,
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            ),
            self._edit_payload(
                invoice,
                amount="120000.00",
                title="UPDATED TITLE ONLY",
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.title,
            "UPDATED TITLE ONLY",
        )
        self.assertFalse(
            invoice.amount_verified
        )
        self.assertFalse(
            invoice.ocr_verified
        )

    def test_repeat_ocr_preserves_manual_confirmation_on_mismatch(self):
        invoice = self._create_invoice(
            amount=Decimal("125000.00"),
            ocr_amount=Decimal("120000.00"),
            amount_verified=True,
            ocr_verified=False,
        )

        warning = apply_ocr_amount_to_invoice(
            invoice,
            "119000.00",
        )

        self.assertEqual(
            invoice.amount,
            Decimal("125000.00"),
        )
        self.assertEqual(
            invoice.ocr_amount,
            Decimal("119000.00"),
        )
        self.assertTrue(
            invoice.amount_verified
        )
        self.assertFalse(
            invoice.ocr_verified
        )
        self.assertIn(
            "Ручное подтверждение сохранено",
            warning,
        )
        self.assertIn(
            "имеет приоритет",
            warning,
        )

    def test_non_positive_manual_amount_is_not_confirmed(self):
        invoice = self._create_invoice()

        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            ),
            self._edit_payload(
                invoice,
                amount="0.00",
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.amount,
            Decimal("0.00"),
        )
        self.assertFalse(
            invoice.amount_verified
        )
        self.assertFalse(
            invoice.ocr_verified
        )
