from .audit_models import InvoiceLog


def create_invoice_log(
    invoice,
    user,
    action
):

    InvoiceLog.objects.create(
        invoice=invoice,
        user=user,
        action=action
    )