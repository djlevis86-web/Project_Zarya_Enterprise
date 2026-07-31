from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..document_field_review_service import (
    DocumentFieldReviewError,
    confirm_invoice_field,
)
from ..log_service import create_invoice_log
from ..models import Invoice


def _redirect_after_confirmation(request, invoice):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
    ):
        return redirect(next_url)
    return redirect("invoice_detail", invoice_id=invoice.id)


@staff_member_required
@require_POST
def confirm_invoice_field_view(request, invoice_id, field_name):
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        is_deleted=False,
    )

    try:
        review = confirm_invoice_field(
            invoice,
            field_name,
            request.user,
            value=request.POST.get("value"),
        )
    except DocumentFieldReviewError as error:
        messages.error(request, str(error))
        return _redirect_after_confirmation(request, invoice)

    create_invoice_log(
        invoice,
        request.user,
        (
            "Поле документа подтверждено: "
            + review.get_field_name_display()
            + "."
        ),
    )
    messages.success(
        request,
        "Поле документа подтверждено.",
    )
    return _redirect_after_confirmation(request, invoice)
