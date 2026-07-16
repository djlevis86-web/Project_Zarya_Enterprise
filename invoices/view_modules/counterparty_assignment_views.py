from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from ..forms import InvoiceCounterpartyAssignForm
from ..log_service import create_invoice_log
from ..models import Counterparty, Invoice


COUNTERPARTY_SEARCH_LIMIT = 30


def get_counterparty_search_queryset(search_query):

    search_query = (
        search_query or ''
    ).strip()

    if not search_query:
        return Counterparty.objects.none()

    return (
        Counterparty.objects
        .filter(
            is_active=True,
            source__in=[
                Counterparty.SOURCE_1C,
                Counterparty.SOURCE_MANUAL,
            ],
        )
        .filter(
            Q(name__icontains=search_query)
            | Q(full_name__icontains=search_query)
            | Q(inn__icontains=search_query)
            | Q(kpp__icontains=search_query)
        )
        .order_by(
            'name',
            'inn',
        )[:COUNTERPARTY_SEARCH_LIMIT]
    )


@staff_member_required
def invoice_assign_counterparty(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        is_deleted=False,
    )

    search_query = (
        request.POST.get(
            'q',
            request.GET.get(
                'q',
                '',
            ),
        )
        or ''
    ).strip()

    counterparties = get_counterparty_search_queryset(
        search_query
    )

    if request.method == 'POST':

        form = InvoiceCounterpartyAssignForm(
            request.POST
        )

        if form.is_valid():

            counterparty = form.cleaned_data[
                'counterparty'
            ]

            invoice.counterparty = counterparty

            invoice.counterparty_match_status = (
                Invoice.COUNTERPARTY_MATCH_FOUND
            )

            invoice.counterparty_match_comment = (
                f'Контрагент привязан вручную: {counterparty.name}'
            )

            invoice.save(
                update_fields=[
                    'counterparty',
                    'counterparty_match_status',
                    'counterparty_match_comment',
                ]
            )

            create_invoice_log(
                invoice,
                request.user,
                f'Контрагент привязан вручную: {counterparty.name}'
            )

            messages.success(
                request,
                'Контрагент успешно привязан к счету.'
            )

            next_url = request.POST.get(
                'next'
            )

            if (
                next_url
                and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={
                        request.get_host(),
                    },
                    require_https=request.is_secure(),
                )
            ):

                return redirect(
                    next_url
                )

            return redirect(
                'invoice_detail',
                invoice_id=invoice.id
            )

    else:

        form = InvoiceCounterpartyAssignForm()

    return render(
        request,
        'invoices/invoice_assign_counterparty.html',
        {
            'invoice': invoice,
            'form': form,
            'search_query': search_query,
            'counterparties': counterparties,
            'counterparty_search_limit': COUNTERPARTY_SEARCH_LIMIT,
        }
    )
