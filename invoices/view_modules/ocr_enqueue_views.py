from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from users.permissions import require_user_permission, user_can_process_invoices
from ..models import Invoice, OCRJob
from ..log_service import create_invoice_log


@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на постановку OCR-задач.')
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
