from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from ..models import Invoice
from ..search_helpers import build_multi_variant_search_q
from .payment_registry_helpers import PAYMENT_STATUS_FILTER_CHOICES, apply_payment_status_filter
from django.utils.dateparse import parse_date


RECENT_INVOICE_FILTERS_SESSION_KEY = 'invoice_list_recent_filters'
RECENT_INVOICE_FILTERS_LIMIT = 5

INVOICE_LIST_RECENT_FILTER_FIELDS = [
    'search',
    'user',
    'status',
    'payment_status',
    'document_type',
    'document_date_from',
    'document_date_to',
    'planned_payment_date_from',
    'planned_payment_date_to',
    'sort',
]


def _short_recent_filter_value(value, max_length=32):

    value = str(
        value or ''
    ).strip()

    if len(value) <= max_length:
        return value

    return f'{value[:max_length - 3]}...'


def _is_meaningful_recent_invoice_filter(filter_params):

    for key, value in filter_params.items():

        if not value:
            continue

        if key == 'sort':
            if value != '-created_at':
                return True

            continue

        return True

    return False


def _build_recent_invoice_filter_querystring(filter_params):

    query_params = {}

    for key in INVOICE_LIST_RECENT_FILTER_FIELDS:
        value = filter_params.get(
            key,
            ''
        )

        if not value:
            continue

        if key == 'sort' and value == '-created_at':
            continue

        query_params[key] = value

    return urlencode(
        query_params
    )


def _build_recent_invoice_filter_label(
    filter_params,
    statuses,
    payment_status_choices,
    document_type_choices,
    users_by_id,
):

    labels = []

    status_labels = dict(
        statuses
    )
    payment_status_labels = dict(
        payment_status_choices
    )
    document_type_labels = dict(
        document_type_choices
    )

    search = filter_params.get(
        'search',
        ''
    )
    if search:
        labels.append(
            f'Поиск: {_short_recent_filter_value(search)}'
        )

    user_id = filter_params.get(
        'user',
        ''
    )
    if user_id:
        labels.append(
            f'Пользователь: {users_by_id.get(user_id, user_id)}'
        )

    status = filter_params.get(
        'status',
        ''
    )
    if status:
        labels.append(
            f'Статус: {status_labels.get(status, status)}'
        )

    payment_status = filter_params.get(
        'payment_status',
        ''
    )
    if payment_status:
        labels.append(
            f'Оплата: {payment_status_labels.get(payment_status, payment_status)}'
        )

    document_type = filter_params.get(
        'document_type',
        ''
    )
    if document_type:
        labels.append(
            f'Тип: {document_type_labels.get(document_type, document_type)}'
        )

    document_date_from = filter_params.get(
        'document_date_from',
        ''
    )
    document_date_to = filter_params.get(
        'document_date_to',
        ''
    )
    if document_date_from or document_date_to:
        labels.append(
            f'Дата документа: {document_date_from or "…"}—{document_date_to or "…"}'
        )

    planned_payment_date_from = filter_params.get(
        'planned_payment_date_from',
        ''
    )
    planned_payment_date_to = filter_params.get(
        'planned_payment_date_to',
        ''
    )
    if planned_payment_date_from or planned_payment_date_to:
        labels.append(
            f'План: {planned_payment_date_from or "…"}—{planned_payment_date_to or "…"}'
        )

    sort = filter_params.get(
        'sort',
        ''
    )
    if sort and sort != '-created_at':
        sort_labels = {
            'created_at': 'Сначала старые',
            '-amount': 'Сумма по убыванию',
            'amount': 'Сумма по возрастанию',
            '-id': 'ID по убыванию',
            'id': 'ID по возрастанию',
            'title': 'Название А—Я',
            '-title': 'Название Я—А',
            'document_date': 'Дата документа по возрастанию',
            '-document_date': 'Дата документа по убыванию',
            'planned_payment_date': 'Плановая оплата по возрастанию',
            '-planned_payment_date': 'Плановая оплата по убыванию',
        }

        labels.append(
            f'Сортировка: {sort_labels.get(sort, sort)}'
        )

    if labels:
        return ' · '.join(
            labels
        )

    return 'Фильтр'


def _update_recent_invoice_filters(
    request,
    filter_params,
    statuses,
    payment_status_choices,
    document_type_choices,
    users_by_id,
):

    recent_filters = request.session.get(
        RECENT_INVOICE_FILTERS_SESSION_KEY,
        []
    )

    if not _is_meaningful_recent_invoice_filter(
        filter_params
    ):
        return recent_filters

    querystring = _build_recent_invoice_filter_querystring(
        filter_params
    )

    if not querystring:
        return recent_filters

    label = _build_recent_invoice_filter_label(
        filter_params,
        statuses,
        payment_status_choices,
        document_type_choices,
        users_by_id,
    )

    recent_filters = [
        recent_filter
        for recent_filter in recent_filters
        if recent_filter.get('querystring') != querystring
    ]

    recent_filters.insert(
        0,
        {
            'label': label,
            'querystring': querystring,
        }
    )

    recent_filters = recent_filters[:RECENT_INVOICE_FILTERS_LIMIT]

    request.session[RECENT_INVOICE_FILTERS_SESSION_KEY] = recent_filters
    request.session.modified = True

    return recent_filters


@login_required
@require_POST
def clear_recent_invoice_filters(request):

    request.session.pop(
        RECENT_INVOICE_FILTERS_SESSION_KEY,
        None
    )
    request.session.modified = True

    return redirect(
        'invoice_list'
    )


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

    in_work_count = stats_queryset.filter(
        status=Invoice.STATUS_IN_WORK
    ).count()

    on_approval_count = stats_queryset.filter(
        status=Invoice.STATUS_ON_APPROVAL
    ).count()

    review_count = in_work_count

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

    users_by_id = {
        str(user.id): user.username
        for user in users
    }

    current_filter_params = {
        'search': search,
        'user': user_filter if request.user.is_staff else '',
        'status': status,
        'payment_status': payment_status_filter,
        'document_type': document_type_filter,
        'document_date_from': document_date_from,
        'document_date_to': document_date_to,
        'planned_payment_date_from': planned_payment_date_from,
        'planned_payment_date_to': planned_payment_date_to,
        'sort': sort,
    }

    recent_invoice_filters = _update_recent_invoice_filters(
        request,
        current_filter_params,
        Invoice.STATUS_CHOICES,
        PAYMENT_STATUS_FILTER_CHOICES,
        Invoice.DOCUMENT_TYPE_CHOICES,
        users_by_id,
    )

    return render(
        request,
        'invoices/invoice_list.html',
        {
            'page_obj': page_obj,
            'querystring_without_page': querystring_without_page,
            'recent_invoice_filters': recent_invoice_filters,
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
            'in_work_count': in_work_count,
            'on_approval_count': on_approval_count,
            'approved_count': approved_count,
            'paid_count': paid_count,
            'rejected_count': rejected_count,
        }
    )
