from .models import Invoice


def auto_approve_invoice(invoice):

    if not invoice.amount:

        invoice.status = Invoice.STATUS_REJECTED

        return (
            Invoice.STATUS_REJECTED,
            'Не удалось определить сумму'
        )

    amount = float(invoice.amount)

    if amount <= 5000:

        invoice.status = Invoice.STATUS_APPROVED

        return (
            Invoice.STATUS_APPROVED,
            'Автоматически подтвержден'
        )

    if amount <= 50000:

        invoice.status = Invoice.STATUS_REVIEW

        return (
            Invoice.STATUS_REVIEW,
            'Требуется проверка менеджером'
        )

    invoice.status = Invoice.STATUS_REVIEW

    return (
        Invoice.STATUS_REVIEW,
        'Большая сумма, требуется согласование'
    )