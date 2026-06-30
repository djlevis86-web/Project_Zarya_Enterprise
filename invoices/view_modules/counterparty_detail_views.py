from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from ..models import Counterparty, Invoice


@staff_member_required
def counterparty_detail(request, counterparty_id):

    counterparty = get_object_or_404(
        Counterparty,
        id=counterparty_id
    )

    invoices = (
        Invoice.objects
        .filter(
            counterparty=counterparty
        )
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    invoices_count = invoices.count()

    unpaid_invoices = invoices.exclude(
        status=Invoice.STATUS_PAID
    )

    unpaid_count = unpaid_invoices.count()

    unpaid_total = (
        unpaid_invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    return render(
        request,
        'invoices/counterparty_detail.html',
        {
            'counterparty': counterparty,
            'invoices': invoices,
            'invoices_count': invoices_count,
            'unpaid_count': unpaid_count,
            'unpaid_total': unpaid_total,
        }
    )
