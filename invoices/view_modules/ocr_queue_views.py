from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from ..models import OCRJob


@login_required
def ocr_queue(request):

    selected_status = request.GET.get(
        'status',
        ''
    )

    jobs = (
        OCRJob.objects
        .select_related(
            'invoice',
            'user',
            'invoice__counterparty',
        )
        .order_by(
            '-created_at'
        )
    )

    if not request.user.is_staff:

        jobs = jobs.filter(
            user=request.user
        )

    if selected_status:

        jobs = jobs.filter(
            status=selected_status
        )

    stats_queryset = OCRJob.objects.all()

    if not request.user.is_staff:

        stats_queryset = stats_queryset.filter(
            user=request.user
        )

    pending_count = stats_queryset.filter(
        status=OCRJob.STATUS_PENDING
    ).count()

    processing_count = stats_queryset.filter(
        status=OCRJob.STATUS_PROCESSING
    ).count()

    done_count = stats_queryset.filter(
        status=OCRJob.STATUS_DONE
    ).count()

    error_count = stats_queryset.filter(
        status=OCRJob.STATUS_ERROR
    ).count()

    paginator = Paginator(
        jobs,
        25
    )

    page_obj = paginator.get_page(
        request.GET.get(
            'page'
        )
    )

    return render(
        request,
        'invoices/ocr_queue.html',
        {
            'page_obj': page_obj,
            'selected_status': selected_status,
            'status_choices': OCRJob.STATUS_CHOICES,
            'pending_count': pending_count,
            'processing_count': processing_count,
            'done_count': done_count,
            'error_count': error_count,
        }
    )
