from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import (
    Invoice,
    InvoicePayment,
    PaymentRegistry,
    PaymentRegistryItem,
)


@login_required
@require_POST
def delete_invoice(request, invoice_id):

    if not request.user.is_staff:
        raise PermissionDenied

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        is_deleted=False,
    )

    has_posted_payments = invoice.payments.filter(
        status=InvoicePayment.STATUS_POSTED,
    ).exists()

    if has_posted_payments:
        messages.error(
            request,
            'Счёт нельзя удалить: по нему есть проведённые платежи.',
        )

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id,
        )

    has_active_registry_items = invoice.payment_registry_items.exclude(
        status=PaymentRegistryItem.STATUS_CANCELLED,
    ).exclude(
        registry__status=PaymentRegistry.STATUS_CANCELLED,
    ).exists()

    if has_active_registry_items:
        messages.error(
            request,
            'Счёт нельзя удалить: он находится в активном реестре оплаты.',
        )

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id,
        )

    invoice.is_deleted = True
    invoice.deleted_at = timezone.now()
    invoice.deleted_by = request.user

    invoice.save(
        update_fields=[
            'is_deleted',
            'deleted_at',
            'deleted_by',
            'updated_at',
        ]
    )

    messages.success(
        request,
        f'Счёт #{invoice.id} удалён из рабочих списков.',
    )

    return redirect(
        'invoice_list'
    )
