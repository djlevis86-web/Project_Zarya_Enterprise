from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from users.permissions import require_user_permission, user_can_process_invoices
from audit.models import AuditLog
from audit.services import log_action
from ..models import Invoice
from ..ocr_processing_service import run_invoice_ocr_processing


@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на повторное OCR-распознавание.')
def repeat_ocr(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if (
        not request.user.is_staff
        and invoice.user_id != request.user.id
    ):

        raise PermissionDenied

    if request.method != 'POST':

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id
        )

    ok, message = run_invoice_ocr_processing(
        invoice,
        request.user,
        'OCR повторно выполнен вручную'
    )

    if ok:

        log_action(
            request=request,
            action=AuditLog.ACTION_OCR,
            obj=invoice,
            message='OCR повторно выполнен вручную.',
            metadata={
                'mode': 'single',
            },
        )

        messages.success(
            request,
            'OCR успешно обновлен.'
        )

        if message and message != 'OCR успешно обновлен':

            messages.warning(
                request,
                message
            )

    else:

        log_action(
            request=request,
            action=AuditLog.ACTION_OCR,
            obj=invoice,
            message=f'OCR повторно не выполнен: {message}',
            metadata={
                'mode': 'single',
                'error': message,
            },
        )

        messages.error(
            request,
            f'OCR не выполнен: {message}'
        )

    return redirect(
        'invoice_detail',
        invoice_id=invoice.id
    )
