from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.counterparty_service import find_counterparty_by_name
from invoices.document_field_review_service import confirm_invoice_field
from invoices.models import Counterparty, Invoice, InvoiceFieldReview


class CounterpartyCompactNameMatchTests(TestCase):
    def test_hyphen_and_quote_spacing_are_equivalent(self):
        expected = Counterparty.objects.create(
            name="АЛЬЯНС-ВЕТ ООО",
            full_name='ООО "АЛЬЯНС-ВЕТ"',
            inn="7722488887",
            kpp="772201001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.assertEqual(
            find_counterparty_by_name("ООО-АЛЬЯНС-ВЕТ"),
            expected,
        )

    def test_legal_form_position_is_matched_by_full_name(self):
        expected = Counterparty.objects.create(
            name="АЛЬЯНС-ВЕТ ООО",
            full_name='ООО "АЛЬЯНС-ВЕТ"',
            source=Counterparty.SOURCE_MANUAL,
            is_active=True,
        )

        self.assertEqual(
            find_counterparty_by_name("ООО АЛЬЯНС ВЕТ"),
            expected,
        )

    def test_different_compact_name_is_not_matched(self):
        Counterparty.objects.create(
            name="АЛЬЯНС-АГРО ООО",
            full_name='ООО "АЛЬЯНС-АГРО"',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.assertIsNone(
            find_counterparty_by_name("ООО-АЛЬЯНС-ВЕТ")
        )


class VendorConfirmationCounterpartyRematchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="vendor-rematch-staff",
            email="vendor-rematch-staff@example.com",
            password="test-password",
            is_staff=True,
        )
        self.invoice = Invoice.objects.create(
            user=self.staff,
            title="Документ повторного сопоставления",
            file="invoices/vendor-rematch.pdf",
            amount=Decimal("39393.75"),
            vendor="СОО-АЛЬЯНС-ВЕТ (2}",
            counterparty_match_status=(
                Invoice.COUNTERPARTY_MATCH_NOT_FOUND
            ),
            counterparty_match_comment=(
                "Контрагент по распознанному названию не найден."
            ),
        )

    def test_confirmed_vendor_assigns_unique_counterparty(self):
        expected = Counterparty.objects.create(
            name="АЛЬЯНС-ВЕТ ООО",
            full_name='ООО "АЛЬЯНС-ВЕТ"',
            inn="7722488887",
            kpp="772201001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
            self.staff,
            value="ООО-АЛЬЯНС-ВЕТ",
        )

        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.vendor, "ООО-АЛЬЯНС-ВЕТ")
        self.assertEqual(self.invoice.counterparty, expected)
        self.assertEqual(
            self.invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_FOUND,
        )
        self.assertEqual(
            self.invoice.counterparty_match_comment,
            (
                "Контрагент найден в справочнике "
                "после подтверждения поставщика."
            ),
        )

    def test_existing_manual_assignment_is_not_overwritten(self):
        existing = Counterparty.objects.create(
            name="Контрагент, назначенный вручную",
            source=Counterparty.SOURCE_MANUAL,
            is_active=True,
        )
        Counterparty.objects.create(
            name="АЛЬЯНС-ВЕТ ООО",
            full_name='ООО "АЛЬЯНС-ВЕТ"',
            inn="7722488887",
            kpp="772201001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )
        self.invoice.counterparty = existing
        self.invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_FOUND
        )
        self.invoice.counterparty_match_comment = (
            "Контрагент назначен вручную."
        )
        self.invoice.save(
            update_fields=(
                "counterparty",
                "counterparty_match_status",
                "counterparty_match_comment",
                "updated_at",
            )
        )

        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
            self.staff,
            value="ООО-АЛЬЯНС-ВЕТ",
        )

        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.counterparty, existing)
        self.assertEqual(
            self.invoice.counterparty_match_comment,
            "Контрагент назначен вручную.",
        )

    def test_confirmation_without_match_keeps_unassigned_state(self):
        previous_comment = self.invoice.counterparty_match_comment

        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_VENDOR,
            self.staff,
            value="ООО Несуществующий поставщик",
        )

        self.invoice.refresh_from_db()

        self.assertIsNone(self.invoice.counterparty)
        self.assertEqual(
            self.invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_NOT_FOUND,
        )
        self.assertEqual(
            self.invoice.counterparty_match_comment,
            previous_comment,
        )

    def test_non_vendor_confirmation_does_not_run_rematch(self):
        Counterparty.objects.create(
            name="АЛЬЯНС-ВЕТ ООО",
            full_name='ООО "АЛЬЯНС-ВЕТ"',
            inn="7722488887",
            kpp="772201001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        confirm_invoice_field(
            self.invoice,
            InvoiceFieldReview.FIELD_INVOICE_NUMBER,
            self.staff,
            value="УТ-357",
        )

        self.invoice.refresh_from_db()

        self.assertIsNone(self.invoice.counterparty)
        self.assertEqual(self.invoice.invoice_number, "УТ-357")
