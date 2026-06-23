from decimal import Decimal

from django.db.models import Sum

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
