from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from ..models import Invoice
from ..search_helpers import build_multi_variant_search_q
from .payment_registry_helpers import PAYMENT_STATUS_FILTER_CHOICES, apply_payment_status_filter
from django.utils.dateparse import parse_date


@login_required
def invoice_list(request):

    User = get_user_model()

    invoices = (
        Invoice.objects
        .select_related(
            'user',
            'counterparty',
        )
        .filter(
            is_deleted=False
        )
    )

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    search = request.GET.get(
        'search',
        ''
    ).strip()

    status = request.GET.get(
        'status',
        ''
    )

    user_filter = request.GET.get(
        'user',
        ''
    )

    payment_status_filter = request.GET.get(
        'payment_status',
        ''
    )

    document_type_filter = request.GET.get(
        'document_type',
        ''
    )

    document_date_from = request.GET.get(
        'document_date_from',
        ''
    )

    document_date_to = request.GET.get(
        'document_date_to',
        ''
    )

    planned_payment_date_from = request.GET.get(
        'planned_payment_date_from',
        ''
    )

    planned_payment_date_to = request.GET.get(
        'planned_payment_date_to',
        ''
    )

    sort = request.GET.get(
        'sort',
        '-created_at'
    )

    if search:

        invoices = invoices.filter(
            build_multi_variant_search_q(
                search,
                [
                    'title',
                    'original_filename',
                    'description',
                    'vendor',
                    'invoice_number',
                    'ocr_text',
                    'user__username',
                    'counterparty__name',
                    'counterparty__full_name',
                    'counterparty__inn',
                    'counterparty__kpp',
                ],
            )
        )

    if status:

        invoices = invoices.filter(
            status=status
        )

    if user_filter and request.user.is_staff:

        invoices = invoices.filter(
            user_id=user_filter
        )

    if document_type_filter:

        invoices = invoices.filter(
            document_type=document_type_filter
        )

    parsed_document_date_from = parse_date(
        document_date_from
    )

    parsed_document_date_to = parse_date(
        document_date_to
    )

    if parsed_document_date_from:

        invoices = invoices.filter(
            document_date__gte=parsed_document_date_from
        )

    if parsed_document_date_to:

        invoices = invoices.filter(
            document_date__lte=parsed_document_date_to
        )

    parsed_planned_payment_date_from = parse_date(
        planned_payment_date_from
    )

    parsed_planned_payment_date_to = parse_date(
        planned_payment_date_to
    )

    if parsed_planned_payment_date_from:

        invoices = invoices.filter(
            planned_payment_date__gte=parsed_planned_payment_date_from
        )

    if parsed_planned_payment_date_to:

        invoices = invoices.filter(
            planned_payment_date__lte=parsed_planned_payment_date_to
        )

    invoices = apply_payment_status_filter(
        invoices,
        payment_status_filter
    )

    allowed_sorts = [
        'id',
        '-id',
        'title',
        '-title',
        'amount',
        '-amount',
        'created_at',
        '-created_at',
        'document_date',
        '-document_date',
        'planned_payment_date',
        '-planned_payment_date',
    ]

    if sort not in allowed_sorts:

        sort = '-created_at'

    invoices = invoices.order_by(
        sort
    )

    paginator = Paginator(
        invoices,
        15
    )

    page_number = request.GET.get(
        'page'
    )

    page_obj = paginator.get_page(
        page_number
    )

    query_params = request.GET.copy()
    query_params.pop(
        'page',
        None
    )
    querystring_without_page = query_params.urlencode()

    stats_queryset = Invoice.objects.filter(
        is_deleted=False
    )

    if not request.user.is_staff:

        stats_queryset = stats_queryset.filter(
            user=request.user
        )

    total_count = stats_queryset.count()

    new_count = stats_queryset.filter(
        status=Invoice.STATUS_NEW
    ).count()

    review_count = stats_queryset.filter(
        status=Invoice.STATUS_REVIEW
    ).count()

    approved_count = stats_queryset.filter(
        status=Invoice.STATUS_APPROVED
    ).count()

    paid_count = stats_queryset.filter(
        status=Invoice.STATUS_PAID
    ).count()

    rejected_count = stats_queryset.filter(
        status=Invoice.STATUS_REJECTED
    ).count()

    users = User.objects.order_by(
        'username'
    )

    return render(
        request,
        'invoices/invoice_list.html',
        {
            'page_obj': page_obj,
            'querystring_without_page': querystring_without_page,
            'search': search,
            'status': status,
            'sort': sort,
            'user_filter': user_filter,
            'payment_status_filter': payment_status_filter,
            'payment_status_choices': PAYMENT_STATUS_FILTER_CHOICES,
            'document_type_filter': document_type_filter,
            'document_type_choices': Invoice.DOCUMENT_TYPE_CHOICES,
            'document_date_from': document_date_from,
            'document_date_to': document_date_to,
            'planned_payment_date_from': planned_payment_date_from,
            'planned_payment_date_to': planned_payment_date_to,
            'statuses': Invoice.STATUS_CHOICES,
            'users': users,
            'total_count': total_count,
            'new_count': new_count,
            'review_count': review_count,
            'approved_count': approved_count,
            'paid_count': paid_count,
            'rejected_count': rejected_count,
        }
    )
