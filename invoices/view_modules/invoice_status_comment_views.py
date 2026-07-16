from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from audit.models import AuditLog
from audit.services import log_action
from ..comment_forms import InvoiceCommentForm
from ..log_service import create_invoice_log
from ..models import Invoice
from ..selectors import get_visible_invoices_for_user


@staff_member_required
@require_POST
def change_invoice_status(request, invoice_id, status):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    allowed_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_IN_WORK,
        Invoice.STATUS_ON_APPROVAL,
        Invoice.STATUS_APPROVED,
        Invoice.STATUS_PAID,
        Invoice.STATUS_REJECTED,
    ]

    if status not in allowed_statuses:

        messages.error(
            request,
            'Недопустимый статус.'
        )

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id
        )

    old_status = invoice.status
    old_status_label = dict(Invoice.STATUS_CHOICES).get(old_status, old_status)
    new_status_label = dict(Invoice.STATUS_CHOICES).get(status, status)

    invoice.status = status

    invoice.save()

    create_invoice_log(
        invoice,
        request.user,
        f'Статус изменён на "{invoice.get_status_display()}"'
    )

    log_action(
        request=request,
        action=AuditLog.ACTION_UPDATE,
        obj=invoice,
        message=f'Статус документа изменён: {old_status_label} -> {new_status_label}.',
        metadata={
            'field': 'status',
            'old_status': old_status,
            'new_status': status,
            'old_status_label': old_status_label,
            'new_status_label': new_status_label,
        },
    )

    messages.success(
        request,
        'Статус успешно изменен.'
    )

    return redirect(
        'invoice_detail',
        invoice_id=invoice.id
    )

@login_required
@require_POST
def add_comment(request, invoice_id):

    invoice = get_object_or_404(
        get_visible_invoices_for_user(
            request.user
        ),
        id=invoice_id,
    )

    form = InvoiceCommentForm(
        request.POST
    )

    if form.is_valid():

        comment = form.save(
            commit=False
        )

        comment.invoice = invoice
        comment.user = request.user

        comment.save()

        create_invoice_log(
            invoice,
            request.user,
            'Добавлен комментарий'
        )

    return redirect(
        'invoice_detail',
        invoice_id=invoice.id
    )
