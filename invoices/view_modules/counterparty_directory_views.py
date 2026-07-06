from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from ..models import Counterparty, Invoice


@staff_member_required
def counterparty_directory(request):

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    source_filter = request.GET.get(
        'source',
        ''
    )

    active_filter = request.GET.get(
        'active',
        'active'
    )

    requisites_filter = request.GET.get(
        'requisites',
        ''
    )

    counterparties = Counterparty.objects.all()

    if active_filter == 'active':

        counterparties = counterparties.filter(
            is_active=True
        )

    elif active_filter == 'inactive':

        counterparties = counterparties.filter(
            is_active=False
        )

    if source_filter:

        counterparties = counterparties.filter(
            source=source_filter
        )

    if search_query:

        counterparties = counterparties.filter(
            Q(name__icontains=search_query)
            |
            Q(full_name__icontains=search_query)
            |
            Q(inn__icontains=search_query)
            |
            Q(kpp__icontains=search_query)
            |
            Q(bank_name__icontains=search_query)
            |
            Q(external_id_1c__icontains=search_query)
        )

    missing_requisites_query = (
        Q(inn__isnull=True)
        |
        Q(inn='')
        |
        Q(bank_name__isnull=True)
        |
        Q(bank_name='')
        |
        Q(bik__isnull=True)
        |
        Q(bik='')
        |
        Q(account_number__isnull=True)
        |
        Q(account_number='')
    )

    if requisites_filter == 'missing':

        counterparties = counterparties.filter(
            missing_requisites_query
        )

    elif requisites_filter == 'complete':

        counterparties = counterparties.exclude(
            missing_requisites_query
        )

    payment_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_IN_WORK,
        Invoice.STATUS_ON_APPROVAL,
        Invoice.STATUS_APPROVED,
    ]

    counterparties = (
        counterparties
        .annotate(
            invoices_count=Count(
                'invoices',
                distinct=True
            ),
            unpaid_invoices_count=Count(
                'invoices',
                filter=Q(
                    invoices__status__in=payment_statuses
                ),
                distinct=True
            ),
            unpaid_total=Sum(
                'invoices__amount',
                filter=Q(
                    invoices__status__in=payment_statuses
                )
            )
        )
        .order_by(
            'name'
        )
    )

    paginator = Paginator(
        counterparties,
        25
    )

    page_number = request.GET.get(
        'page'
    )

    page_obj = paginator.get_page(
        page_number
    )

    query_params = request.GET.copy()

    if 'page' in query_params:

        query_params.pop(
            'page'
        )

    return render(
        request,
        'invoices/counterparty_directory.html',
        {
            'page_obj': page_obj,
            'search_query': search_query,
            'source_filter': source_filter,
            'active_filter': active_filter,
            'requisites_filter': requisites_filter,
            'source_choices': Counterparty.SOURCE_CHOICES,
            'query_string': query_params.urlencode(),
        }
    )
