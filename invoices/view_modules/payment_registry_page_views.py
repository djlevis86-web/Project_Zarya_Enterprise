from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from users.permissions import require_user_permission, user_can_process_invoices
from django.utils.dateparse import parse_date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .payment_registry_helpers import (
    OCR_STATUS_FILTER_CHOICES,
    PAYMENT_STATUS_FILTER_CHOICES,
    apply_ocr_status_filter,
    apply_payment_status_filter,
    apply_positive_payment_balance_filter,
    get_payment_registry_permission_context,
)

from ..models import (
    CompanyRequisites,
    Counterparty,
    Invoice,
    InvoicePayment,
    PaymentRegistry,
    PaymentRegistryItem,
)

from ..search_helpers import build_multi_variant_search_q
from ..enterprise_analytics_services import (
    build_enterprise_payment_schedule_analytics,
    build_enterprise_registry_analytics,
    enterprise_analytics_to_primitive,
)
from ..presentation_services import (
    annotate_invoice_workspace,
    build_presentations,
)
from ..selectors import get_visible_invoices_for_user

from ..payment_registry_permissions import (
    require_payment_registry_permission,
    user_can_cancel_payment_registry,
    user_can_check_payment_registry,
    user_can_export_payment_registry,
    user_can_manage_payment_registry,
    user_can_mark_payment_registry_paid,
)


PAYMENT_SCHEDULE_PAGE_SIZE = 12
PAYMENT_REGISTRY_PAGE_SIZE = 25
PAYMENT_SCHEDULE_CHART_MAX_DAYS = 31

PAYMENT_SCHEDULE_FILTERS = {
    'all',
    'today',
    'week',
    'month',
    'overdue',
    'no_date',
}


def _query_string(
    request,
    *,
    overrides=None,
    remove=(),
):
    query = request.GET.copy()

    for key in remove:
        query.pop(
            key,
            None,
        )

    for key, value in (
        overrides
        or {}
    ).items():
        if value in (
            None,
            '',
        ):
            query.pop(
                key,
                None,
            )
        else:
            query[key] = str(
                value
            )

    encoded = query.urlencode()

    return (
        f'?{encoded}'
        if encoded
        else ''
    )


def _pagination_query_string(
    request,
):
    return _query_string(
        request,
        remove=(
            'page',
        ),
    ).lstrip(
        '?'
    )


def _schedule_period_links(
    request,
    *,
    filter_type,
):
    links = []

    for value, label in (
        (
            'week',
            'Неделя',
        ),
        (
            'month',
            'Месяц',
        ),
        (
            'all',
            'Все',
        ),
    ):
        links.append(
            {
                'value': value,
                'label': label,
                'is_active': (
                    filter_type
                    == value
                ),
                'query_string': (
                    _query_string(
                        request,
                        overrides={
                            'filter': value,
                        },
                        remove=(
                            'page',
                            'date_from',
                            'date_to',
                        ),
                    )
                ),
            }
        )

    return links


def _schedule_metric_cards(
    request,
    metrics,
):
    cards = []

    for metric in metrics:
        metric_filters = dict(
            metric.filters
        )

        if metric.code == 'total':
            metric_filters['filter'] = 'all'

        cards.append(
            {
                'metric': metric,
                'query_string': (
                    _query_string(
                        request,
                        overrides=metric_filters,
                        remove=(
                            'page',
                            'date_from',
                            'date_to',
                        ),
                    )
                ),
            }
        )

    return cards


def _schedule_chart_period(
    *,
    filter_type,
    today,
    parsed_date_from,
    parsed_date_to,
):
    if filter_type == 'today':
        default_days = 1
    elif filter_type == 'week':
        default_days = 7
    else:
        default_days = 30

    if filter_type == 'overdue':
        period_end = (
            parsed_date_to
            or (
                today
                - timedelta(
                    days=1
                )
            )
        )
        period_start = (
            parsed_date_from
            or (
                period_end
                - timedelta(
                    days=default_days - 1
                )
            )
        )
    else:
        period_start = (
            parsed_date_from
            or today
        )
        period_end = (
            parsed_date_to
            or (
                period_start
                + timedelta(
                    days=default_days - 1
                )
            )
        )

    if period_end < period_start:
        period_end = period_start

    requested_days = (
        period_end
        - period_start
    ).days + 1

    period_days = min(
        requested_days,
        PAYMENT_SCHEDULE_CHART_MAX_DAYS,
    )

    return (
        period_start,
        period_days,
        requested_days > period_days,
    )


@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на просмотр графика платежей.')
def payment_schedule(request):

    filter_type = request.GET.get(
        'filter',
        'all'
    )

    if filter_type not in PAYMENT_SCHEDULE_FILTERS:
        filter_type = 'all'

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    selected_status = request.GET.get(
        'status',
        'payment'
    )

    valid_statuses = {
        'payment',
        'all',
        *(
            value
            for value, _label
            in Invoice.STATUS_CHOICES
        ),
    }

    if selected_status not in valid_statuses:
        selected_status = 'payment'

    selected_priority = request.GET.get(
        'priority',
        ''
    )

    schedule_payment_status_filter = request.GET.get(
        'payment_status',
        ''
    )

    date_from = request.GET.get(
        'date_from',
        ''
    )

    date_to = request.GET.get(
        'date_to',
        ''
    )

    parsed_date_from = (
        parse_date(
            date_from
        )
        if date_from
        else None
    )

    parsed_date_to = (
        parse_date(
            date_to
        )
        if date_to
        else None
    )

    payment_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_IN_WORK,
        Invoice.STATUS_ON_APPROVAL,
        Invoice.STATUS_APPROVED,
    ]

    base_invoices = (
        get_visible_invoices_for_user(
            request.user
        )
        .filter(
            status__in=payment_statuses
        )
    )

    today = timezone.localdate()

    week_end = (
        today
        + timedelta(
            days=6
        )
    )

    month_end = (
        today
        + timedelta(
            days=29
        )
    )

    scoped_invoices = base_invoices

    if (
        selected_status
        and selected_status
        not in [
            'payment',
            'all',
        ]
    ):
        scoped_invoices = (
            scoped_invoices
            .filter(
                status=selected_status
            )
        )

    if selected_priority:
        scoped_invoices = (
            scoped_invoices
            .filter(
                payment_priority=selected_priority
            )
        )

    scoped_invoices = (
        apply_payment_status_filter(
            scoped_invoices,
            schedule_payment_status_filter
        )
    )

    if search_query:
        scoped_invoices = (
            scoped_invoices
            .filter(
                Q(
                    invoice_number__icontains=search_query
                )
                |
                Q(
                    vendor__icontains=search_query
                )
                |
                Q(
                    counterparty__name__icontains=search_query
                )
                |
                Q(
                    original_filename__icontains=search_query
                )
                |
                Q(
                    title__icontains=search_query
                )
                |
                Q(
                    description__icontains=search_query
                )
            )
        )

    scoped_invoices = (
        apply_positive_payment_balance_filter(
            scoped_invoices
        )
    )

    metric_analytics = (
        build_enterprise_payment_schedule_analytics(
            scoped_invoices,
            today=today,
            period_start=today,
            period_days=7,
            largest_payment_limit=0,
        )
    )

    metric_by_code = {
        metric.code: metric
        for metric
        in metric_analytics.metrics
    }

    total_count = (
        metric_by_code[
            'total'
        ].count
    )

    today_count = (
        metric_by_code[
            'today'
        ].count
    )

    week_count = (
        metric_by_code[
            'week'
        ].count
    )

    overdue_count = (
        metric_by_code[
            'overdue'
        ].count
    )

    no_date_count = (
        metric_by_code[
            'no_date'
        ].count
    )

    month_count = (
        scoped_invoices
        .filter(
            planned_payment_date__gte=today,
            planned_payment_date__lte=month_end
        )
        .count()
    )

    total_amount = (
        scoped_invoices
        .aggregate(
            total=Sum(
                'payment_outstanding_amount'
            )
        )
        .get(
            'total'
        )
        or Decimal(
            '0.00'
        )
    )

    filtered_invoices = scoped_invoices

    if filter_type == 'today':
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date=today
            )
        )

    elif filter_type == 'week':
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date__gte=today,
                planned_payment_date__lte=week_end
            )
        )

    elif filter_type == 'month':
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date__gte=today,
                planned_payment_date__lte=month_end
            )
        )

    elif filter_type == 'overdue':
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date__lt=today
            )
        )

    elif filter_type == 'no_date':
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date__isnull=True
            )
        )

    if (
        parsed_date_from
        and filter_type != 'no_date'
    ):
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date__gte=parsed_date_from
            )
        )

    if (
        parsed_date_to
        and filter_type != 'no_date'
    ):
        filtered_invoices = (
            filtered_invoices
            .filter(
                planned_payment_date__lte=parsed_date_to
            )
        )

    filtered_count = (
        filtered_invoices
        .count()
    )

    filtered_amount = (
        filtered_invoices
        .aggregate(
            total=Sum(
                'payment_outstanding_amount'
            )
        )
        .get(
            'total'
        )
        or Decimal(
            '0.00'
        )
    )

    (
        chart_period_start,
        chart_period_days,
        schedule_chart_limited,
    ) = _schedule_chart_period(
        filter_type=filter_type,
        today=today,
        parsed_date_from=parsed_date_from,
        parsed_date_to=parsed_date_to,
    )

    schedule_analytics = (
        build_enterprise_payment_schedule_analytics(
            filtered_invoices,
            today=today,
            period_start=chart_period_start,
            period_days=chart_period_days,
            largest_payment_limit=5,
        )
    )

    schedule_payload = (
        enterprise_analytics_to_primitive(
            schedule_analytics
        )
    )

    chart_payment_series = (
        schedule_payload.get(
            'payment_series',
            []
        )
    )

    charted_amount = sum(
        (
            Decimal(
                str(
                    point.get(
                        'amount'
                    )
                    or '0.00'
                )
            )
            for point
            in chart_payment_series
        ),
        Decimal(
            '0.00'
        ),
    )

    charted_count = sum(
        (
            int(
                point.get(
                    'count'
                )
                or 0
            )
            for point
            in chart_payment_series
        ),
        0,
    )

    chart_outside_amount = max(
        filtered_amount
        - charted_amount,
        Decimal(
            '0.00'
        ),
    )

    chart_outside_count = max(
        filtered_count
        - charted_count,
        0,
    )

    priority_field = Invoice._meta.get_field(
        'payment_priority'
    )

    priority_choices = list(
        priority_field.choices or []
    )

    if not priority_choices:
        priority_choices = [
            (
                item,
                item
            )
            for item in (
                base_invoices
                .exclude(
                    payment_priority__isnull=True
                )
                .order_by(
                    '-payment_priority'
                )
                .values_list(
                    'payment_priority',
                    flat=True
                )
                .distinct()
            )
        ]

    ordered_invoices = (
        annotate_invoice_workspace(
            filtered_invoices
        )
        .order_by(
            'planned_payment_date',
            '-payment_priority',
            'counterparty__name',
            'id'
        )
    )

    nearest_payment = (
        annotate_invoice_workspace(
            filtered_invoices.filter(
                planned_payment_date__gte=today
            )
        )
        .order_by(
            'planned_payment_date',
            '-payment_priority',
            'counterparty__name',
            'id'
        )
        .first()
    )

    if nearest_payment is not None:
        build_presentations(
            [
                nearest_payment,
            ],
            today=today,
        )

    paginator = Paginator(
        ordered_invoices,
        PAYMENT_SCHEDULE_PAGE_SIZE,
    )

    page_obj = paginator.get_page(
        request.GET.get(
            'page'
        )
    )

    invoices = list(
        page_obj.object_list
    )

    build_presentations(
        invoices,
        today=today,
    )

    schedule_period_links = (
        _schedule_period_links(
            request,
            filter_type=filter_type,
        )
    )

    schedule_metric_cards = (
        _schedule_metric_cards(
            request,
            metric_analytics.metrics,
        )
    )

    return render(
        request,
        'invoices/payment_schedule.html',
        {
            'invoices': invoices,
            'nearest_payment': nearest_payment,
            'page_obj': page_obj,
            'pagination_query': (
                _pagination_query_string(
                    request
                )
            ),
            'today': today,
            'week_end': week_end,
            'month_end': month_end,
            'filter_type': filter_type,
            'search_query': search_query,
            'selected_status': selected_status,
            'selected_priority': selected_priority,
            'schedule_payment_status_filter': schedule_payment_status_filter,
            'payment_status_choices': PAYMENT_STATUS_FILTER_CHOICES,
            'date_from': date_from,
            'date_to': date_to,
            'status_choices': Invoice.STATUS_CHOICES,
            'priority_choices': priority_choices,
            'total_count': total_count,
            'today_count': today_count,
            'week_count': week_count,
            'month_count': month_count,
            'overdue_count': overdue_count,
            'no_date_count': no_date_count,
            'total_amount': total_amount,
            'filtered_count': filtered_count,
            'filtered_amount': filtered_amount,
            'charted_count': charted_count,
            'charted_amount': charted_amount,
            'chart_outside_count': chart_outside_count,
            'chart_outside_amount': chart_outside_amount,
            'schedule_metrics': metric_analytics.metrics,
            'schedule_metric_cards': schedule_metric_cards,
            'schedule_period_links': schedule_period_links,
            'schedule_analytics': schedule_analytics,
            'schedule_payload': schedule_payload,
            'schedule_chart_limited': schedule_chart_limited,
        }
    )

@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на просмотр реестра оплаты.')
def payment_registry_detail(request, registry_id):

    from ..models import PaymentRegistry, PaymentRegistryItem
    from ..payment_registry_services import (
        check_payment_registry,
        payment_registry_can_be_edited,
    )

    registry = (
        PaymentRegistry.objects
        .select_related(
            'created_by',
            'checked_by',
            'exported_by',
        )
        .filter(
            id=registry_id,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Реестр оплаты не найден.'
        )

        return redirect(
            'payment_registry_history'
        )

    if not request.user.is_staff and registry.created_by_id != request.user.id:

        messages.warning(
            request,
            'Нет доступа к этому реестру.'
        )

        return redirect(
            'payment_registry_history'
        )

    registry_items = (
        registry.items
        .select_related(
            'invoice',
            'invoice__counterparty',
            'invoice__user',
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            'planned_payment_date',
            'invoice_id',
        )
    )

    check_result = None

    if registry.status == PaymentRegistry.STATUS_DRAFT:

        check_result = check_payment_registry(
            registry
        )

    registry_items = list(
        registry_items
    )
    registry_analytics = (
        build_enterprise_registry_analytics(
            registry,
            items=registry_items,
            check_result=check_result,
        )
    )

    can_edit_registry = payment_registry_can_be_edited(
        registry
    )
    permission_context = (
        get_payment_registry_permission_context(
            request.user
        )
    )

    return render(
        request,
        'invoices/payment_registry_detail.html',
        {
            'page_title': f'Реестр оплаты №{registry.id}',
            'registry': registry,
            'registry_items': registry_items,
            'check_result': check_result,
            'can_edit_registry': can_edit_registry,
            'registry_analytics': registry_analytics,
            **permission_context,
        }
    )

@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на просмотр истории реестров оплаты.')
def payment_registry_history(request):

    from django.core.paginator import Paginator
    from django.db.models import Sum, Q

    from ..models import PaymentRegistry

    status_filter = request.GET.get(
        'status',
        ''
    ).strip()

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    registries = (
        PaymentRegistry.objects
        .select_related(
            'created_by',
            'checked_by',
            'exported_by',
        )
        .all()
        .order_by(
            '-created_at',
        )
    )

    if not request.user.is_staff:

        registries = registries.filter(
            created_by=request.user,
        )

    if status_filter:

        registries = registries.filter(
            status=status_filter,
        )

    if search_query:

        registries = registries.filter(
            Q(title__icontains=search_query)
            | Q(comment__icontains=search_query)
            | Q(created_by__username__icontains=search_query)
            | Q(exported_by__username__icontains=search_query)
        )

    total_registries = registries.count()

    total_amount = (
        registries.aggregate(
            total=Sum('total_amount')
        ).get('total')
        or 0
    )

    draft_count = registries.filter(
        status=PaymentRegistry.STATUS_DRAFT,
    ).count()

    exported_count = registries.filter(
        status=PaymentRegistry.STATUS_EXPORTED,
    ).count()

    paid_count = registries.filter(
        status=PaymentRegistry.STATUS_PAID,
    ).count()

    paginator = Paginator(
        registries,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get('page')
    )

    permission_context = (
        get_payment_registry_permission_context(
            request.user
        )
    )

    return render(
        request,
        'invoices/payment_registry_history.html',
        {
            'page_title': 'История реестров оплаты',
            'page_obj': page_obj,
            'registries': page_obj.object_list,
            'status_filter': status_filter,
            'search_query': search_query,
            'status_choices': PaymentRegistry.STATUS_CHOICES,
            'total_registries': total_registries,
            'total_amount': total_amount,
            'draft_count': draft_count,
            'exported_count': exported_count,
            'paid_count': paid_count,
            **permission_context,
        }
    )

@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на работу с реестром оплаты.')
def payment_registry(request):

    selected_status = request.GET.get(
        'status',
        Invoice.STATUS_APPROVED
    )

    valid_statuses = {
        'all',
        *(
            value
            for value, _label
            in Invoice.STATUS_CHOICES
        ),
    }

    if selected_status not in valid_statuses:
        selected_status = Invoice.STATUS_APPROVED

    selected_counterparty = request.GET.get(
        'counterparty',
        ''
    )

    registry_payment_status_filter = request.GET.get(
        'payment_status',
        ''
    )

    ocr_status_filter = request.GET.get(
        'ocr_status',
        ''
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    date_from = request.GET.get(
        'date_from',
        ''
    ).strip()

    date_to = request.GET.get(
        'date_to',
        ''
    ).strip()

    from ..models import PaymentRegistry, PaymentRegistryItem
    from ..payment_registry_services import ACTIVE_REGISTRY_STATUSES, check_payment_registry, get_active_editable_payment_registry, validate_invoice_for_payment_registry

    draft_registry = get_active_editable_payment_registry()
    draft_registry_created = False

    draft_registry_items = PaymentRegistryItem.objects.none()
    draft_registry_check_result = None

    if draft_registry:

        draft_registry_items = (
            draft_registry.items
            .select_related(
                'invoice',
                'invoice__counterparty',
                'invoice__user',
            )
            .exclude(
                status=PaymentRegistryItem.STATUS_CANCELLED
            )
            .order_by(
                'planned_payment_date',
                'invoice_id',
            )
        )

        draft_registry_check_result = check_payment_registry(
            draft_registry
        )

    active_registry_invoice_ids = (
        PaymentRegistryItem.objects
        .filter(
            registry__status__in=ACTIVE_REGISTRY_STATUSES,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .values_list(
            'invoice_id',
            flat=True,
        )
    )

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .exclude(
            status=Invoice.STATUS_PAID
        )
        .exclude(
            id__in=active_registry_invoice_ids
        )
    )

    if selected_status and selected_status != 'all':

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_counterparty:

        invoices = invoices.filter(
            counterparty_id=selected_counterparty
        )

    invoices = apply_payment_status_filter(
        invoices,
        registry_payment_status_filter
    )

    invoices = apply_ocr_status_filter(
        invoices,
        ocr_status_filter
    )

    if search_query:

        invoices = invoices.filter(
            build_multi_variant_search_q(
                search_query,
                [
                    'title',
                    'original_filename',
                    'invoice_number',
                    'vendor',
                    'counterparty__name',
                    'counterparty__full_name',
                    'counterparty__inn',
                    'counterparty__kpp',
                ],
            )
        )

    if date_from:

        invoices = invoices.filter(
            planned_payment_date__gte=date_from
        )

    if date_to:

        invoices = invoices.filter(
            planned_payment_date__lte=date_to
        )

    invoices = apply_positive_payment_balance_filter(
        invoices
    )

    total_count = invoices.count()

    total_amount = (
        invoices.aggregate(
            total=Sum(
                'payment_outstanding_amount'
            )
        ).get(
            'total'
        )
        or Decimal(
            '0.00'
        )
    )

    ordered_invoices = (
        annotate_invoice_workspace(
            invoices
        )
        .order_by(
            'planned_payment_date',
            '-payment_priority',
            'counterparty__name',
            'id'
        )
    )

    paginator = Paginator(
        ordered_invoices,
        PAYMENT_REGISTRY_PAGE_SIZE,
    )

    page_obj = paginator.get_page(
        request.GET.get(
            'page'
        )
    )

    invoices = list(
        page_obj.object_list
    )

    build_presentations(
        invoices
    )

    readiness_blocked_count = 0

    for invoice in invoices:
        readiness_errors, readiness_warnings = validate_invoice_for_payment_registry(
            invoice
        )

        invoice.payment_registry_block_errors = readiness_errors
        invoice.payment_registry_warning_messages = readiness_warnings
        invoice.payment_registry_is_ready = not readiness_errors

        if readiness_errors:
            readiness_blocked_count += 1

    ready_page_count = sum(
        1
        for invoice in invoices
        if invoice.payment_registry_is_ready
    )
    registry_return_query = (
        request.GET.urlencode()
    )

    # OCR_REGISTRY_SUMMARY_CONTEXT_V3
    ocr_registry_draft_items = list(draft_registry_items or [])
    draft_registry_items = ocr_registry_draft_items

    ocr_registry_invoice_map = {}

    for item in ocr_registry_draft_items:
        if item.invoice_id:
            ocr_registry_invoice_map[item.invoice_id] = item.invoice

    for invoice in list(invoices or []):
        if invoice.id:
            ocr_registry_invoice_map[invoice.id] = invoice

    ocr_registry_invoices = list(ocr_registry_invoice_map.values())
    ocr_registry_items_count = len(ocr_registry_invoices)
    ocr_registry_ready_count = sum(
        1
        for invoice in ocr_registry_invoices
        if invoice.amount_verified
    )
    ocr_registry_errors_count = sum(
        1
        for invoice in ocr_registry_invoices
        if not invoice.amount_verified
    )

    registry_analytics = None

    if draft_registry:
        registry_analytics = (
            build_enterprise_registry_analytics(
                draft_registry,
                items=draft_registry_items,
                check_result=(
                    draft_registry_check_result
                ),
            )
        )

    permission_context = (
        get_payment_registry_permission_context(
            request.user
        )
    )

    return render(
        request,
        'invoices/payment_registry.html',
        {
            'invoices': invoices,
            'page_obj': page_obj,
            'pagination_query': (
                _pagination_query_string(
                    request
                )
            ),
            'registry_return_query': registry_return_query,
            'ready_page_count': ready_page_count,
            'total_count': total_count,
            'total_amount': total_amount,
            'selected_status': selected_status,
            'selected_counterparty': selected_counterparty,
            'registry_payment_status_filter': registry_payment_status_filter,
            'payment_status_choices': PAYMENT_STATUS_FILTER_CHOICES,
            'ocr_status_filter': ocr_status_filter,
            'ocr_status_choices': OCR_STATUS_FILTER_CHOICES,
            'search_query': search_query,
            'date_from': date_from,
            'date_to': date_to,
            'status_choices': Invoice.STATUS_CHOICES,
            'draft_registry': draft_registry,
            'draft_registry_items': draft_registry_items,
            "ocr_registry_items_count": ocr_registry_items_count,
            "ocr_registry_ready_count": ocr_registry_ready_count,
            "ocr_registry_errors_count": ocr_registry_errors_count,
            "readiness_blocked_count": readiness_blocked_count,
            'draft_registry_items_count': draft_registry.items_count if draft_registry else 0,
            'draft_registry_total_amount': draft_registry.total_amount if draft_registry else 0,
            'draft_registry_check_result': draft_registry_check_result,
            'registry_analytics': registry_analytics,
            **permission_context,
        }
    )
