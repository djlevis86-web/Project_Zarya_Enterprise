from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from ..models import Invoice
from ..enterprise_analytics_services import (
    build_enterprise_dashboard_analytics,
)
from ..search_helpers import build_multi_variant_search_q
from .payment_registry_helpers import PAYMENT_STATUS_FILTER_CHOICES, apply_payment_status_filter
from django.utils import timezone
from django.utils.dateparse import parse_date

from users.permissions import user_can_view_all_invoices

from ..models import ResponsiblePerson
from ..presentation_services import (
    READINESS_FILTER_CHOICES,
    annotate_invoice_workspace,
    build_dashboard_workspace,
    build_presentations,
)
from ..selectors import get_visible_invoices_for_user


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

@login_required
def invoice_list(request):
    User = get_user_model()

    invoices = get_visible_invoices_for_user(
        request.user
    )

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "")
    user_filter = request.GET.get("user", "")
    payment_status_filter = request.GET.get(
        "payment_status",
        "",
    )
    document_type_filter = request.GET.get(
        "document_type",
        "",
    )
    responsible_filter = request.GET.get(
        "responsible",
        "",
    )
    readiness_filter = request.GET.get(
        "readiness",
        "",
    )
    document_date_from = request.GET.get(
        "document_date_from",
        "",
    )
    document_date_to = request.GET.get(
        "document_date_to",
        "",
    )
    planned_payment_date_from = request.GET.get(
        "planned_payment_date_from",
        "",
    )
    planned_payment_date_to = request.GET.get(
        "planned_payment_date_to",
        "",
    )
    sort = request.GET.get("sort", "-created_at")

    if search:
        invoices = invoices.filter(
            build_multi_variant_search_q(
                search,
                [
                    "title",
                    "original_filename",
                    "description",
                    "vendor",
                    "invoice_number",
                    "ocr_text",
                    "user__username",
                    "counterparty__name",
                    "counterparty__full_name",
                    "counterparty__inn",
                    "counterparty__kpp",
                    "responsible__full_name",
                ],
            )
        )

    if status:
        invoices = invoices.filter(status=status)

    if user_filter and user_can_view_all_invoices(request.user):
        invoices = invoices.filter(user_id=user_filter)

    if document_type_filter:
        invoices = invoices.filter(
            document_type=document_type_filter
        )

    if responsible_filter:
        invoices = invoices.filter(
            responsible_id=responsible_filter
        )

    parsed_document_date_from = parse_date(
        document_date_from
    )
    parsed_document_date_to = parse_date(
        document_date_to
    )
    parsed_planned_payment_date_from = parse_date(
        planned_payment_date_from
    )
    parsed_planned_payment_date_to = parse_date(
        planned_payment_date_to
    )

    if parsed_document_date_from:
        invoices = invoices.filter(
            document_date__gte=parsed_document_date_from
        )
    if parsed_document_date_to:
        invoices = invoices.filter(
            document_date__lte=parsed_document_date_to
        )
    if parsed_planned_payment_date_from:
        invoices = invoices.filter(
            planned_payment_date__gte=(
                parsed_planned_payment_date_from
            )
        )
    if parsed_planned_payment_date_to:
        invoices = invoices.filter(
            planned_payment_date__lte=(
                parsed_planned_payment_date_to
            )
        )

    invoices = apply_payment_status_filter(
        invoices,
        payment_status_filter,
    )
    invoices = annotate_invoice_workspace(invoices)

    today = timezone.localdate()

    if readiness_filter == "attention":
        invoices = invoices.filter(
            Q(amount__lte=0)
            | Q(amount_verified=False)
            | Q(document_type=Invoice.DOCUMENT_TYPE_UNKNOWN)
            | Q(counterparty__isnull=True)
            | Q(responsible__isnull=True)
            | Q(
                status=Invoice.STATUS_APPROVED,
                planned_payment_date__isnull=True,
            )
            | Q(counterparty__inn__isnull=True)
            | Q(counterparty__inn="")
            | Q(counterparty__bank_name__isnull=True)
            | Q(counterparty__bank_name="")
            | Q(counterparty__account_number__isnull=True)
            | Q(counterparty__account_number="")
            | Q(counterparty__bik__isnull=True)
            | Q(counterparty__bik="")
        )
    elif readiness_filter == "ready":
        invoices = (
            invoices
            .filter(
                status=Invoice.STATUS_APPROVED,
                amount__gt=0,
                amount_verified=True,
                counterparty__isnull=False,
                responsible__isnull=False,
                planned_payment_date__isnull=False,
                paid_at__isnull=True,
                active_registry_id__isnull=True,
                payment_paid_sum__lt=F("amount"),
            )
            .exclude(
                document_type=Invoice.DOCUMENT_TYPE_UNKNOWN,
            )
            .exclude(counterparty__inn__isnull=True)
            .exclude(counterparty__inn="")
            .exclude(counterparty__bank_name__isnull=True)
            .exclude(counterparty__bank_name="")
            .exclude(counterparty__account_number__isnull=True)
            .exclude(counterparty__account_number="")
            .exclude(counterparty__bik__isnull=True)
            .exclude(counterparty__bik="")
        )
    elif readiness_filter == "overdue":
        invoices = invoices.filter(
            planned_payment_date__lt=today,
            payment_paid_sum__lt=F("amount"),
        )
    elif readiness_filter == "in_registry":
        invoices = invoices.filter(
            active_registry_id__isnull=False,
        )

    allowed_sorts = [
        "id",
        "-id",
        "title",
        "-title",
        "amount",
        "-amount",
        "created_at",
        "-created_at",
        "document_date",
        "-document_date",
        "planned_payment_date",
        "-planned_payment_date",
    ]
    if sort not in allowed_sorts:
        sort = "-created_at"

    invoices = invoices.order_by(sort, "-id")
    paginator = Paginator(invoices, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )
    build_presentations(
        page_obj.object_list,
        today=today,
    )

    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring_without_page = query_params.urlencode()

    stats_items = list(
        annotate_invoice_workspace(
            get_visible_invoices_for_user(
                request.user
            )
        ).order_by("-created_at", "-id")
    )
    stats = build_dashboard_workspace(
        stats_items,
        today=today,
    )

    users = User.objects.order_by("username")
    responsibles = ResponsiblePerson.objects.filter(
        is_active=True
    ).order_by("full_name", "id")
    users_by_id = {
        str(user.id): user.username
        for user in users
    }

    current_filter_params = {
        "search": search,
        "user": (
            user_filter
            if user_can_view_all_invoices(request.user)
            else ""
        ),
        "status": status,
        "payment_status": payment_status_filter,
        "document_type": document_type_filter,
        "document_date_from": document_date_from,
        "document_date_to": document_date_to,
        "planned_payment_date_from": (
            planned_payment_date_from
        ),
        "planned_payment_date_to": (
            planned_payment_date_to
        ),
        "sort": sort,
    }
    recent_invoice_filters = _update_recent_invoice_filters(
        request,
        current_filter_params,
        Invoice.STATUS_CHOICES,
        PAYMENT_STATUS_FILTER_CHOICES,
        Invoice.DOCUMENT_TYPE_CHOICES,
        users_by_id,
    )

    enterprise_list_analytics = (
        build_enterprise_dashboard_analytics(
            get_visible_invoices_for_user(
                request.user
            ),
            today=today,
            series_days=7,
            task_limit=0,
            recent_activity_limit=0,
            largest_payment_limit=0,
        )
    )
    enterprise_metrics = {
        metric.code: metric
        for metric in enterprise_list_analytics.metrics
    }

    return render(
        request,
        "invoices/invoice_list.html",
        {
            "page_obj": page_obj,
            "querystring_without_page": querystring_without_page,
            "recent_invoice_filters": recent_invoice_filters,
            "search": search,
            "status": status,
            "sort": sort,
            "user_filter": user_filter,
            "payment_status_filter": payment_status_filter,
            "payment_status_choices": PAYMENT_STATUS_FILTER_CHOICES,
            "document_type_filter": document_type_filter,
            "document_type_choices": Invoice.DOCUMENT_TYPE_CHOICES,
            "responsible_filter": responsible_filter,
            "responsibles": responsibles,
            "readiness_filter": readiness_filter,
            "readiness_choices": READINESS_FILTER_CHOICES,
            "document_date_from": document_date_from,
            "document_date_to": document_date_to,
            "planned_payment_date_from": planned_payment_date_from,
            "planned_payment_date_to": planned_payment_date_to,
            "statuses": Invoice.STATUS_CHOICES,
            "users": users,
            "total_count": stats["total_count"],
            "attention_count": stats["attention_count"],
            "ready_count": stats["ready_count"],
            "overdue_count": stats["overdue_count"],
            "paid_count": stats["paid_month_count"],
            "enterprise_list_analytics": enterprise_list_analytics,
            "enterprise_metrics": enterprise_metrics,
            "new_count": sum(
                1
                for invoice in stats_items
                if invoice.status == Invoice.STATUS_NEW
            ),
            "review_count": sum(
                1
                for invoice in stats_items
                if invoice.status == Invoice.STATUS_IN_WORK
            ),
            "in_work_count": sum(
                1
                for invoice in stats_items
                if invoice.status == Invoice.STATUS_IN_WORK
            ),
            "on_approval_count": sum(
                1
                for invoice in stats_items
                if invoice.status == Invoice.STATUS_ON_APPROVAL
            ),
            "approved_count": sum(
                1
                for invoice in stats_items
                if invoice.status == Invoice.STATUS_APPROVED
            ),
            "rejected_count": sum(
                1
                for invoice in stats_items
                if invoice.status == Invoice.STATUS_REJECTED
            ),
        },
    )
