from .models import Invoice
from .readiness_services import evaluate_document_readiness


def auto_approve_invoice(invoice):

    if not invoice.amount:

        invoice.status = Invoice.STATUS_REJECTED

        return (
            Invoice.STATUS_REJECTED,
            'Не удалось определить сумму'
        )

    amount = float(invoice.amount)

    if amount <= 5000:

        readiness = evaluate_document_readiness(
            invoice
        )

        if not readiness.can_approve:
            invoice.status = Invoice.STATUS_IN_WORK
            primary = readiness.primary_blocker
            message = (
                primary.message
                if primary
                else "Требуется проверка данных документа."
            )
            return (
                Invoice.STATUS_IN_WORK,
                "Документ требует проверки: " + message,
            )

        invoice.status = Invoice.STATUS_APPROVED

        return (
            Invoice.STATUS_APPROVED,
            'Автоматически утверждён'
        )

    if amount <= 50000:

        invoice.status = Invoice.STATUS_IN_WORK

        return (
            Invoice.STATUS_IN_WORK,
            'Требуется работа менеджера'
        )

    invoice.status = Invoice.STATUS_ON_APPROVAL

    return (
        Invoice.STATUS_ON_APPROVAL,
        'Большая сумма, требуется согласование'
    )
