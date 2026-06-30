from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from audit.models import AuditLog
from audit.services import log_action

from ..models import Invoice, OCRJob
from ..ocr_processing_service import run_invoice_ocr_processing


from .ocr_repeat_views import (
    repeat_ocr,
)

from .ocr_queue_views import (
    ocr_queue,
)


@login_required
def bulk_repeat_ocr(request):

    if request.method != 'POST':

        return redirect(
            'invoice_list'
        )

    next_url = request.POST.get(
        'next',
        ''
    )

    invoice_ids = [
        item
        for item in request.POST.getlist(
            'invoice_ids'
        )
        if item
    ]

    if not invoice_ids:

        messages.warning(
            request,
            'Выберите хотя бы один счет для повторного OCR.'
        )

        if next_url.startswith(
            '/'
        ):

            return redirect(
                next_url
            )

        return redirect(
            'invoice_list'
        )

    invoices = (
        Invoice.objects
        .filter(
            id__in=invoice_ids
        )
        .select_related(
            'user',
            'counterparty'
        )
        .order_by(
            'id'
        )
    )

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    allowed_count = invoices.count()
    requested_count = len(
        invoice_ids
    )

    if allowed_count == 0:

        messages.error(
            request,
            'Нет доступных счетов для повторного OCR.'
        )

        if next_url.startswith(
            '/'
        ):

            return redirect(
                next_url
            )

        return redirect(
            'invoice_list'
        )

    success_count = 0
    error_items = []
    warning_items = []

    for invoice in invoices:

        ok, message = run_invoice_ocr_processing(
            invoice,
            request.user,
            'OCR повторно выполнен массово'
        )

        if ok:

            success_count += 1

            if message and message != 'OCR успешно обновлен':

                warning_items.append(
                    f'#{invoice.id}: {message}'
                )

        else:

            error_items.append(
                f'#{invoice.id}: {message}'
            )

    log_action(
        request=request,
        action=AuditLog.ACTION_OCR,
        object_type='Invoice',
        object_repr='Массовый OCR',
        message='Массовый OCR выбранных счетов выполнен.',
        metadata={
            'mode': 'bulk',
            'requested_count': requested_count,
            'allowed_count': allowed_count,
            'success_count': success_count,
            'error_count': len(error_items),
            'warning_count': len(warning_items),
            'requested_invoice_ids': invoice_ids,
        },
    )

    if success_count:

        messages.success(
            request,
            f'OCR выполнен для счетов: {success_count}.'
        )

    if requested_count != allowed_count:

        messages.warning(
            request,
            (
                'Часть выбранных счетов была пропущена: '
                'нет доступа или счет не найден.'
            )
        )

    if warning_items:

        messages.warning(
            request,
            'Предупреждения OCR: ' + ' | '.join(
                warning_items[:5]
            )
        )

    if error_items:

        messages.error(
            request,
            'Ошибки OCR: ' + ' | '.join(
                error_items[:5]
            )
        )

    if next_url.startswith(
        '/'
    ):

        return redirect(
            next_url
        )

    return redirect(
        'invoice_list'
    )

@login_required
def enqueue_ocr_jobs(request):

    if request.method != 'POST':

        return redirect(
            'invoice_list'
        )

    next_url = request.POST.get(
        'next',
        ''
    )

    invoice_ids = request.POST.getlist(
        'invoice_ids'
    )

    single_invoice_id = request.POST.get(
        'invoice_id'
    )

    if single_invoice_id:

        invoice_ids.append(
            single_invoice_id
        )

    invoice_ids = [
        item
        for item in invoice_ids
        if item
    ]

    if not invoice_ids:

        messages.warning(
            request,
            'Выберите хотя бы один счет для постановки OCR в очередь.'
        )

        if next_url.startswith(
            '/'
        ):

            return redirect(
                next_url
            )

        return redirect(
            'invoice_list'
        )

    invoices = (
        Invoice.objects
        .filter(
            id__in=invoice_ids
        )
        .select_related(
            'user'
        )
        .order_by(
            'id'
        )
    )

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    created_count = 0
    skipped_count = 0

    for invoice in invoices:

        existing_job = (
            OCRJob.objects
            .filter(
                invoice=invoice,
                status__in=[
                    OCRJob.STATUS_PENDING,
                    OCRJob.STATUS_PROCESSING,
                ]
            )
            .first()
        )

        if existing_job:

            skipped_count += 1

            continue

        OCRJob.objects.create(
            invoice=invoice,
            user=request.user,
            status=OCRJob.STATUS_PENDING,
            source=OCRJob.SOURCE_BULK,
        )

        create_invoice_log(
            invoice,
            request.user,
            'OCR поставлен в очередь'
        )

        created_count += 1

    if created_count:

        messages.success(
            request,
            f'OCR поставлен в очередь: {created_count}.'
        )

    if skipped_count:

        messages.warning(
            request,
            f'Пропущено, уже есть активная OCR задача: {skipped_count}.'
        )

    if next_url.startswith(
        '/'
    ):

        return redirect(
            next_url
        )

    return redirect(
        'ocr_queue'
    )
