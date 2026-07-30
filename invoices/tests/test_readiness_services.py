from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from invoices.approval_service import auto_approve_invoice
from invoices.models import Invoice
from invoices.readiness_services import (
    evaluate_document_readiness,
    evaluate_payment_readiness,
)


def ready_counterparty():
    return SimpleNamespace(
        inn="3525001001",
        bank_name="ТЕСТОВЫЙ БАНК",
        account_number="40702810000000000001",
        bik="044705615",
    )


def ready_invoice(**overrides):
    values = {
        "amount": Decimal("1000.00"),
        "amount_verified": True,
        "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
        "counterparty_id": 10,
        "counterparty": ready_counterparty(),
        "responsible_id": 20,
        "invoice_number": "617",
        "document_date": date(2026, 7, 7),
        "invoice_date": "",
        "planned_payment_date": date(2026, 7, 17),
        "status": Invoice.STATUS_APPROVED,
        "paid_at": None,
        "is_deleted": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class DocumentReadinessTests(SimpleTestCase):
    def test_ready_document_can_be_approved(self):
        result = evaluate_document_readiness(
            ready_invoice(status=Invoice.STATUS_ON_APPROVAL)
        )
        self.assertTrue(result.can_approve)
        self.assertEqual(result.blockers, ())
        self.assertFalse(result.is_legacy_repair)
        self.assertEqual(result.next_action, "Утвердить документ")

    def test_incomplete_approved_document_is_repair_state(self):
        result = evaluate_document_readiness(
            ready_invoice(
                amount=Decimal("0.00"),
                amount_verified=False,
                counterparty_id=None,
                counterparty=None,
                responsible_id=None,
                status=Invoice.STATUS_APPROVED,
            )
        )
        self.assertFalse(result.can_approve)
        self.assertTrue(result.is_legacy_repair)
        self.assertEqual(
            [issue.code for issue in result.blockers],
            [
                "amount_missing",
                "amount_unverified",
                "counterparty_missing",
                "responsible_missing",
            ],
        )

    def test_number_date_and_plan_are_approval_warnings(self):
        result = evaluate_document_readiness(
            ready_invoice(
                invoice_number="",
                document_date=None,
                invoice_date="",
                planned_payment_date=None,
                status=Invoice.STATUS_ON_APPROVAL,
            )
        )
        self.assertTrue(result.can_approve)
        self.assertEqual(
            [issue.code for issue in result.warnings],
            [
                "invoice_number_missing",
                "document_date_missing",
                "planned_payment_date_missing",
            ],
        )


    def test_complete_small_document_is_auto_approved(self):
        invoice = ready_invoice(
            status=Invoice.STATUS_NEW,
        )

        status, message = auto_approve_invoice(
            invoice
        )

        self.assertEqual(
            status,
            Invoice.STATUS_APPROVED,
        )
        self.assertEqual(
            invoice.status,
            Invoice.STATUS_APPROVED,
        )
        self.assertIn(
            "Автоматически",
            message,
        )


class PaymentReadinessTests(SimpleTestCase):
    def test_without_payment_summary_does_not_assume_balance(
        self,
    ):
        result = evaluate_payment_readiness(
            ready_invoice()
        )

        self.assertTrue(
            result.can_add_to_registry
        )
        self.assertIsNone(
            result.remaining_amount
        )
        self.assertEqual(
            result.warnings,
            (),
        )

    def test_ready_document_can_enter_registry(self):
        result = evaluate_payment_readiness(
            ready_invoice(),
            payment_summary={"remaining_amount": Decimal("1000.00")},
        )
        self.assertTrue(result.can_add_to_registry)
        self.assertFalse(result.is_legacy_repair)
        self.assertEqual(result.blockers, ())

    def test_document_blockers_are_reused(self):
        result = evaluate_payment_readiness(
            ready_invoice(
                amount_verified=False,
                counterparty_id=None,
                counterparty=None,
            ),
            payment_summary={"remaining_amount": Decimal("1000.00")},
        )
        codes = {issue.code for issue in result.blockers}
        self.assertTrue(result.is_legacy_repair)
        self.assertIn("amount_unverified", codes)
        self.assertIn("counterparty_missing", codes)

    def test_plan_and_requisites_are_required(self):
        result = evaluate_payment_readiness(
            ready_invoice(
                planned_payment_date=None,
                counterparty=SimpleNamespace(
                    inn="3525001001",
                    bank_name="ТЕСТОВЫЙ БАНК",
                    account_number="",
                    bik="",
                ),
            ),
            payment_summary={"remaining_amount": Decimal("1000.00")},
        )
        self.assertIn(
            "Не указана плановая дата оплаты.",
            result.blocker_messages,
        )
        self.assertIn(
            "У контрагента не заполнено: расчётный счёт, БИК.",
            result.blocker_messages,
        )

    def test_duplicate_and_zero_balance_are_blocked(self):
        result = evaluate_payment_readiness(
            ready_invoice(),
            active_registry_id=17,
            payment_summary={"remaining_amount": Decimal("0.00")},
        )
        self.assertIn(
            "Документ уже есть в реестре №17.",
            result.blocker_messages,
        )
        self.assertIn(
            "Документ уже полностью оплачен или имеет переплату.",
            result.blocker_messages,
        )
