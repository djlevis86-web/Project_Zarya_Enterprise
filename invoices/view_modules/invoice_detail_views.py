from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from users.permissions import user_can_process_invoices

from ..access_policy import user_can_manage_invoice_data
from ..comment_forms import InvoiceCommentForm
from ..comment_models import InvoiceComment
from ..document_field_review_service import (
    build_invoice_field_review_workspace,
)
from ..forms import InvoicePaymentForm
from ..invoice_action_context import (
    get_invoice_detail_action_context,
)
from ..models import InvoicePayment
from ..presentation_services import (
    annotate_invoice_workspace,
    build_invoice_presentation,
    humanize_invoice_log_action,
)
from ..selectors import get_visible_invoices_for_user


@login_required
def invoice_detail(request, invoice_id):
    invoice = get_object_or_404(
        annotate_invoice_workspace(
            get_visible_invoices_for_user(
                request.user
            )
        ),
        id=invoice_id,
    )

    workspace = build_invoice_presentation(
        invoice
    )
    payment_summary = workspace["payment"]
    field_review_workspace = build_invoice_field_review_workspace(
        invoice,
        invoice.field_reviews.select_related("confirmed_by").all(),
    )

    payments = (
        invoice.payments
        .filter(
            status=InvoicePayment.STATUS_POSTED
        )
        .select_related("created_by")
        .order_by("-paid_at", "-created_at")
    )
    comments = (
        InvoiceComment.objects
        .filter(invoice=invoice)
        .select_related("user")
        .order_by("-created_at")
    )
    action_context = get_invoice_detail_action_context(
        request.user,
        invoice,
    )
    action_context["can_manage_invoice_payments"] = bool(
        user_can_manage_invoice_data(request.user)
    )

    workflow_codes = (
        "new",
        "in_work",
        "on_approval",
        "approved",
        "paid",
    )
    workflow_labels = {
        "new": "Новый",
        "in_work": "В работе",
        "on_approval": "На согласовании",
        "approved": "Утверждён",
        "paid": "Оплачен",
    }
    current_workflow_position = (
        workflow_codes.index(invoice.status)
        if invoice.status in workflow_codes
        else -1
    )
    workflow_steps = [
        {
            "code": code,
            "label": workflow_labels[code],
            "is_complete": bool(
                current_workflow_position > position
            ),
            "is_current": bool(
                current_workflow_position == position
            ),
        }
        for position, code in enumerate(
            workflow_codes
        )
    ]

    return render(
        request,
        "invoices/detail.html",
        {
            "invoice": invoice,
            "workspace": workspace,
            "document_readiness": workspace[
                "document_readiness"
            ],
            "payment_readiness": workspace[
                "payment_readiness"
            ],
            "logs": [
                {
                    "created_at": log.created_at,
                    "action": humanize_invoice_log_action(
                        log.action
                    ),
                }
                for log in invoice.logs.all()
            ],
            "comments": comments,
            "comment_form": InvoiceCommentForm(),
            "payment_summary": payment_summary,
            "payments": payments,
            "payment_form": InvoicePaymentForm(),
            "workflow_steps": workflow_steps,
            "field_review_workspace": field_review_workspace,
            "can_confirm_invoice_fields": bool(
                user_can_manage_invoice_data(
                    request.user
                )
            ),
            **action_context,
        },
    )
