from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.counterparty_service import find_counterparty_by_name, get_or_create_counterparty_from_invoice
from invoices.models import Counterparty, Invoice


class CounterpartyMatchingTests(TestCase):
    def test_get_or_create_counterparty_falls_back_to_name_without_supplier_inn(self):
        user = get_user_model().objects.create_user(
            username="counterparty-fallback-user",
            password="pass",
        )

        counterparty = Counterparty.objects.create(
            name="БЕЛЫЙ КЛЕВЕР ООО",
            inn="5321188917",
            kpp="532101001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        invoice = Invoice.objects.create(
            user=user,
            title="UPD fallback test",
            original_filename="upd.pdf",
            file=SimpleUploadedFile(
                "upd.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            vendor="ООО БЕЛЫЙ КЛЕВЕР",
            ocr_text="Универсальный передаточный документ без читаемого ИНН продавца",
        )

        found = get_or_create_counterparty_from_invoice(
            invoice
        )

        self.assertEqual(
            found,
            counterparty,
        )

        self.assertEqual(
            invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_FOUND,
        )

    def test_matches_counterparty_when_legal_form_word_order_differs(self):
        counterparty = Counterparty.objects.create(
            name="БЕЛЫЙ КЛЕВЕР ООО",
            inn="5321188917",
            kpp="532101001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        found = find_counterparty_by_name(
            "ООО БЕЛЫЙ КЛЕВЕР"
        )

        self.assertEqual(
            found,
            counterparty,
        )

    pass
