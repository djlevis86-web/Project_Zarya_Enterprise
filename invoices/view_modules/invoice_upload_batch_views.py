from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from ..models import InvoiceUploadBatch
from ..enterprise_analytics_services import (
    build_enterprise_upload_journal_analytics,
)
from ..presentation_services import (
    annotate_invoice_workspace,
    build_presentations,
)



@login_required
def upload_batches(request):
    status_filter = request.GET.get(
        "status",
        "",
    ).strip()
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    base_batches = (
        InvoiceUploadBatch.objects
        .select_related("user")
        .order_by("-created_at", "-id")
    )

    if not request.user.is_staff:
        base_batches = base_batches.filter(
            user=request.user
        )

    upload_analytics = (
        build_enterprise_upload_journal_analytics(
            base_batches,
            recent_limit=10,
        )
    )

    batches = base_batches

    if status_filter:
        batches = batches.filter(
            status=status_filter
        )

    if search_query:
        search_filter = Q(
            user__username__icontains=search_query
        )

        if search_query.isdigit():
            search_filter |= Q(
                id=int(search_query)
            )

        batches = batches.filter(
            search_filter
        )

    paginator = Paginator(
        batches,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "invoices/upload_batches.html",
        {
            "page_obj": page_obj,
            "upload_analytics": upload_analytics,
            "status_filter": status_filter,
            "search_query": search_query,
            "status_choices": InvoiceUploadBatch.STATUS_CHOICES,
            "querystring_without_page": query_params.urlencode(),
        },
    )


@login_required
def upload_batch_detail(request, batch_id):
    batch = get_object_or_404(
        InvoiceUploadBatch.objects.select_related(
            "user"
        ),
        id=batch_id,
    )

    if (
        not request.user.is_staff
        and batch.user_id != request.user.id
    ):
        raise PermissionDenied

    invoices = list(
        annotate_invoice_workspace(
            batch.invoices.all()
        ).order_by(
            "-created_at",
            "-id",
        )
    )
    build_presentations(invoices)

    batch_analytics = (
        build_enterprise_upload_journal_analytics(
            InvoiceUploadBatch.objects.filter(
                id=batch.id
            ),
            recent_limit=1,
        )
    )

    return render(
        request,
        "invoices/upload_batch_detail.html",
        {
            "batch": batch,
            "invoices": invoices,
            "batch_analytics": batch_analytics,
        },
    )
