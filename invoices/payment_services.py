from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import InvoicePayment


PAYMENT_STATUS_UNPAID = "unpaid"
PAYMENT_STATUS_PARTIAL = "partial"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_OVERPAID = "overpaid"


PAYMENT_STATUS_LABELS = {
    PAYMENT_STATUS_UNPAID: "Не оплачен",
    PAYMENT_STATUS_PARTIAL: "Частично оплачен",
    PAYMENT_STATUS_PAID: "Оплачен",
    PAYMENT_STATUS_OVERPAID: "Переплата",
}


def get_invoice_payment_summary(invoice):
    invoice_amount = invoice.amount or Decimal("0.00")

    paid_amount = (
        invoice.payments
        .filter(status=InvoicePayment.STATUS_POSTED)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0.00")
    )

    remaining_amount = invoice_amount - paid_amount

    if paid_amount <= 0:
        payment_status = PAYMENT_STATUS_UNPAID
    elif paid_amount < invoice_amount:
        payment_status = PAYMENT_STATUS_PARTIAL
    elif paid_amount == invoice_amount:
        payment_status = PAYMENT_STATUS_PAID
    else:
        payment_status = PAYMENT_STATUS_OVERPAID

    return {
        "invoice_amount": invoice_amount,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount,
        "payment_status": payment_status,
        "payment_status_label": PAYMENT_STATUS_LABELS[payment_status],
    }


def invoice_has_payment_balance(invoice):
    summary = get_invoice_payment_summary(invoice)

    return summary["remaining_amount"] > Decimal("0.00")

def create_invoice_payment(
    invoice,
    amount,
    user=None,
    registry_item=None,
    paid_at=None,
    payment_number="",
    comment="",
    source=None,
):
    amount = Decimal(str(amount or "0.00"))

    if amount <= 0:
        raise ValueError("Сумма оплаты должна быть больше нуля.")

    summary = get_invoice_payment_summary(invoice)
    remaining_amount = summary["remaining_amount"]

    if remaining_amount <= 0:
        raise ValueError("Счёт уже полностью оплачен или имеет переплату.")

    if amount > remaining_amount:
        raise ValueError(
            f"Сумма оплаты больше остатка по счёту. Остаток: {remaining_amount}."
        )

    payment = InvoicePayment.objects.create(
        invoice=invoice,
        registry_item=registry_item,
        amount=amount,
        paid_at=paid_at or timezone.localdate(),
        payment_number=payment_number or "",
        comment=comment or "",
        created_by=user,
        source=source or InvoicePayment.SOURCE_MANUAL,
        status=InvoicePayment.STATUS_POSTED,
    )

    updated_summary = get_invoice_payment_summary(invoice)

    return payment, updated_summary
