from __future__ import annotations

from users.permissions import (
    user_can_approve_invoices,
    user_can_process_invoices,
    user_is_invoice_uploader,
)

from .models import Invoice
from .payment_registry_services import (
    get_active_registry_items_for_invoice,
)


UPLOADER_EDITABLE_STATUSES = frozenset({
    Invoice.STATUS_NEW,
    Invoice.STATUS_IN_WORK,
    Invoice.STATUS_ON_APPROVAL,
})


def user_can_manage_invoice_data(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or user_can_process_invoices(user)
        )
    )


def invoice_has_active_registry(invoice) -> bool:
    return get_active_registry_items_for_invoice(
        invoice
    ).exists()


def user_can_edit_invoice(user, invoice) -> bool:
    if not user.is_authenticated:
        return False

    if invoice.is_deleted:
        return False

    if user_can_manage_invoice_data(user):
        return True

    if not user_is_invoice_uploader(user):
        return False

    if invoice.user_id != user.id:
        return False

    if invoice.status not in UPLOADER_EDITABLE_STATUSES:
        return False

    return not invoice_has_active_registry(invoice)


def user_can_add_invoice_comment(user, invoice) -> bool:
    if not user.is_authenticated:
        return False

    if invoice.is_deleted:
        return False

    if user_can_manage_invoice_data(user):
        return True

    return bool(
        user_is_invoice_uploader(user)
        and invoice.user_id == user.id
    )


def user_can_approve_invoice(user, invoice) -> bool:
    if not user.is_authenticated:
        return False

    if invoice.is_deleted:
        return False

    if not (
        user.is_staff
        or user.is_superuser
        or user_can_approve_invoices(user)
    ):
        return False

    if invoice.status != Invoice.STATUS_ON_APPROVAL:
        return False

    return not invoice_has_active_registry(invoice)
