from .models import Invoice


def get_visible_invoices_for_user(user):
    invoices = Invoice.objects.filter(
        is_deleted=False,
    )

    if not user.is_authenticated:
        return invoices.none()

    if user.is_staff:
        return invoices

    return invoices.filter(
        user=user,
    )
