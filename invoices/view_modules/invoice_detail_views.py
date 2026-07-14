from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from ..comment_forms import InvoiceCommentForm
from ..comment_models import InvoiceComment
from ..forms import InvoicePaymentForm
from ..models import Invoice, InvoicePayment
from ..payment_services import get_invoice_payment_summary


@login_required
def invoice_detail(request, invoice_id):

    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'user',
            'responsible',
            'counterparty',
        ),
        id=invoice_id,
        is_deleted=False
    )

    if (
        not request.user.is_staff
        and invoice.user != request.user
    ):

        raise PermissionDenied





    payment_summary = get_invoice_payment_summary(
        invoice
    )

    payments = (
        invoice.payments
        .filter(
            status=InvoicePayment.STATUS_POSTED
        )
        .select_related(
            "created_by"
        )
        .order_by(
            "-paid_at",
            "-created_at"
        )
    )

    payment_form = InvoicePaymentForm()

    comments = (
        InvoiceComment.objects
        .filter(
            invoice=invoice
        )
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    comment_form = InvoiceCommentForm()

    return render(
        request,
        'invoices/detail.html',
        {
            'invoice': invoice,
            'logs': invoice.logs.all(),
            'comments': comments,
            'comment_form': comment_form,
            'payment_summary': payment_summary,
            'payments': payments,
            'payment_form': payment_form,
        }
    )
