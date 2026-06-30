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

from ..payment_registry_permissions import (
    require_payment_registry_permission,
    user_can_cancel_payment_registry,
    user_can_check_payment_registry,
    user_can_export_payment_registry,
    user_can_manage_payment_registry,
    user_can_mark_payment_registry_paid,
)


@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на просмотр графика платежей.')
def payment_schedule(request):

    filter_type = request.GET.get(
        'filter',
        'all'
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    selected_status = request.GET.get(
        'status',
        'payment'
    )

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

    parsed_date_from = parse_date(date_from) if date_from else None

    parsed_date_to = parse_date(date_to) if date_to else None

    payment_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_REVIEW,
        Invoice.STATUS_APPROVED,
    ]

    base_invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .filter(
            status__in=payment_statuses
        )
    )

    today = date.today()

    week_end = today + timedelta(
        days=7
    )

    month_end = today + timedelta(
        days=30
    )

    total_count = base_invoices.count()

    today_count = base_invoices.filter(
        planned_payment_date=today
    ).count()

    week_count = base_invoices.filter(
        planned_payment_date__gte=today,
        planned_payment_date__lte=week_end
    ).count()

    month_count = base_invoices.filter(
        planned_payment_date__gte=today,
        planned_payment_date__lte=month_end
    ).count()

    overdue_count = base_invoices.filter(
        planned_payment_date__lt=today
    ).count()

    no_date_count = base_invoices.filter(
        planned_payment_date__isnull=True
    ).count()

    total_amount = (
        base_invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    invoices = base_invoices

    if filter_type == 'today':

        invoices = invoices.filter(
            planned_payment_date=today
        )

    elif filter_type == 'week':

        invoices = invoices.filter(
            planned_payment_date__gte=today,
            planned_payment_date__lte=week_end
        )

    elif filter_type == 'month':

        invoices = invoices.filter(
            planned_payment_date__gte=today,
            planned_payment_date__lte=month_end
        )

    elif filter_type == 'overdue':

        invoices = invoices.filter(
            planned_payment_date__lt=today
        )

    elif filter_type == 'no_date':

        invoices = invoices.filter(
            planned_payment_date__isnull=True
        )

    if selected_status and selected_status not in [
        'payment',
        'all',
    ]:

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_priority:

        invoices = invoices.filter(
            payment_priority=selected_priority
        )

    invoices = apply_payment_status_filter(
        invoices,
        schedule_payment_status_filter
    )

    if parsed_date_from and filter_type != 'no_date':

        invoices = invoices.filter(
            planned_payment_date__gte=parsed_date_from
        )

    if parsed_date_to and filter_type != 'no_date':

        invoices = invoices.filter(
            planned_payment_date__lte=parsed_date_to
        )

    if search_query:

        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(title__icontains=search_query)
            |
            Q(description__icontains=search_query)
        )

    filtered_count = invoices.count()

    filtered_amount = (
        invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
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

    invoices = apply_positive_payment_balance_filter(
        invoices
    )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
    )

    return render(
        request,
        'invoices/payment_schedule.html',
        {
            'invoices': invoices,
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
        }
    )

@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на просмотр реестра оплаты.')
def payment_registry_detail(request, registry_id):

    from ..models import PaymentRegistry, PaymentRegistryItem
    from ..payment_registry_services import check_payment_registry

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

    return render(
        request,
        'invoices/payment_registry_detail.html',
        {
            'page_title': f'Реестр оплаты №{registry.id}',
            'registry': registry,
            'registry_items': registry_items,
            'check_result': check_result,
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
        }
    )

@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на работу с реестром оплаты.')
def payment_registry(request):

    selected_status = request.GET.get(
        'status',
        Invoice.STATUS_APPROVED
    )

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
    from ..payment_registry_services import ACTIVE_REGISTRY_STATUSES, check_payment_registry

    from ..payment_registry_services import (
        get_or_create_draft_payment_registry,
    )

    draft_registry, draft_registry_created = get_or_create_draft_payment_registry(request.user)

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
            Q(title__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
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

    total_amount = (
        invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    counterparties = (
        Counterparty.objects
        .filter(
            invoices__isnull=False
        )
        .distinct()
        .order_by(
            'name'
        )
    )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
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

    return render(
        request,
        'invoices/payment_registry.html',
        {
            'invoices': invoices,
            'counterparties': counterparties,
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
            'draft_registry_items_count': draft_registry.items_count if draft_registry else 0,
            'draft_registry_total_amount': draft_registry.total_amount if draft_registry else 0,
            'draft_registry_check_result': draft_registry_check_result,
        }
    )
