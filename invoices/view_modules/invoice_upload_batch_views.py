from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from ..models import InvoiceUploadBatch


@login_required
def upload_batches(request):

    batches = (
        InvoiceUploadBatch.objects
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    if not request.user.is_staff:

        batches = batches.filter(
            user=request.user
        )

    paginator = Paginator(
        batches,
        20
    )

    page_obj = paginator.get_page(
        request.GET.get(
            'page'
        )
    )

    return render(
        request,
        'invoices/upload_batches.html',
        {
            'page_obj': page_obj,
        }
    )

@login_required
def upload_batch_detail(request, batch_id):

    batch = get_object_or_404(
        InvoiceUploadBatch.objects.select_related(
            'user'
        ),
        id=batch_id
    )

    if not request.user.is_staff and batch.user_id != request.user.id:

        raise PermissionDenied

    invoices = (
        batch.invoices
        .select_related(
            'counterparty',
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    return render(
        request,
        'invoices/upload_batch_detail.html',
        {
            'batch': batch,
            'invoices': invoices,
        }
    )
