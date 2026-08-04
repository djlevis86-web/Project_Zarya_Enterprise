from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, Mapping

from django.db.models import QuerySet
from django.utils import timezone

from .audit_models import InvoiceLog
from .models import (
    Invoice,
    InvoiceUploadBatch,
    PaymentRegistry,
    PaymentRegistryItem,
)
from .presentation_services import (
    annotate_invoice_workspace,
    build_presentations,
    humanize_invoice_log_action,
)


MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.1")

PAYMENT_CANDIDATE_STATUSES = (
    Invoice.STATUS_NEW,
    Invoice.STATUS_IN_WORK,
    Invoice.STATUS_ON_APPROVAL,
    Invoice.STATUS_APPROVED,
)

REGISTRY_LIFECYCLE = (
    (
        PaymentRegistry.STATUS_DRAFT,
        "Черновик",
    ),
    (
        PaymentRegistry.STATUS_CHECKED,
        "Проверен",
    ),
    (
        PaymentRegistry.STATUS_EXPORTED,
        "Выгружен",
    ),
    (
        PaymentRegistry.STATUS_PARTIALLY_PAID,
        "Частично оплачен",
    ),
    (
        PaymentRegistry.STATUS_PAID,
        "Оплачен",
    ),
)


@dataclass(frozen=True)
class EnterpriseMetric:
    code: str
    label: str
    count: int
    amount: Decimal
    tone: str
    filters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class EnterpriseStatusSlice:
    code: str
    label: str
    count: int
    document_amount: Decimal
    outstanding_amount: Decimal
    share_percent: Decimal


@dataclass(frozen=True)
class EnterprisePaymentPoint:
    day: date
    label: str
    count: int
    amount: Decimal
    bucket: str


@dataclass(frozen=True)
class EnterpriseTaskItem:
    invoice_id: int
    title: str
    counterparty_label: str
    responsible_label: str
    planned_payment_date: date | None
    amount: Decimal
    remaining_amount: Decimal
    readiness_code: str
    readiness_label: str
    readiness_tone: str
    reason: str
    next_action: str
    urgency_rank: int


@dataclass(frozen=True)
class EnterpriseActivityItem:
    log_id: int
    invoice_id: int
    title: str
    action: str
    actor_label: str
    created_at: datetime


@dataclass(frozen=True)
class EnterprisePaymentItem:
    invoice_id: int
    title: str
    counterparty_label: str
    planned_payment_date: date
    remaining_amount: Decimal
    readiness_code: str
    readiness_label: str


@dataclass(frozen=True)
class EnterpriseDashboardAnalytics:
    metrics: tuple[EnterpriseMetric, ...]
    status_distribution: tuple[
        EnterpriseStatusSlice,
        ...,
    ]
    payment_series: tuple[
        EnterprisePaymentPoint,
        ...,
    ]
    tasks: tuple[EnterpriseTaskItem, ...]
    recent_actions: tuple[
        EnterpriseActivityItem,
        ...,
    ]
    largest_payments: tuple[
        EnterprisePaymentItem,
        ...,
    ]
    total_documents: int
    total_document_amount: Decimal
    total_outstanding_amount: Decimal
    task_scope: str


@dataclass(frozen=True)
class EnterprisePaymentScheduleAnalytics:
    metrics: tuple[EnterpriseMetric, ...]
    payment_series: tuple[
        EnterprisePaymentPoint,
        ...,
    ]
    largest_payments: tuple[
        EnterprisePaymentItem,
        ...,
    ]
    period_start: date
    period_end: date


@dataclass(frozen=True)
class EnterpriseUploadBatchItem:
    batch_id: int
    created_at: datetime
    user_label: str
    status_code: str
    status_label: str
    total_files: int
    uploaded_count: int
    duplicate_count: int
    skipped_count: int


@dataclass(frozen=True)
class EnterpriseUploadJournalAnalytics:
    total_batches: int
    completed_batches: int
    partial_batches: int
    empty_batches: int
    total_files: int
    uploaded_files: int
    duplicate_files: int
    skipped_files: int
    success_rate: Decimal
    recent_batches: tuple[
        EnterpriseUploadBatchItem,
        ...,
    ]


@dataclass(frozen=True)
class EnterpriseRegistryLifecycleStep:
    code: str
    label: str
    position: int
    is_complete: bool
    is_current: bool


@dataclass(frozen=True)
class EnterpriseRegistryStatusSlice:
    code: str
    label: str
    count: int
    amount: Decimal


@dataclass(frozen=True)
class EnterpriseRegistryIssue:
    invoice_id: int
    title: str
    messages: tuple[str, ...]


@dataclass(frozen=True)
class EnterpriseRegistryAnalytics:
    registry_id: int | None
    status_code: str
    status_label: str
    lifecycle: tuple[
        EnterpriseRegistryLifecycleStep,
        ...,
    ]
    item_count: int
    stored_item_count: int
    calculated_total_amount: Decimal
    stored_total_amount: Decimal
    is_item_count_consistent: bool
    is_total_amount_consistent: bool
    ready_count: int
    blocked_count: int
    errors_count: int
    warnings_count: int
    check_available: bool
    status_distribution: tuple[
        EnterpriseRegistryStatusSlice,
        ...,
    ]
    issues: tuple[EnterpriseRegistryIssue, ...]


def _money(value: object) -> Decimal:
    if value is None:
        return Decimal("0.00")

    return Decimal(
        str(value)
    ).quantize(
        MONEY_QUANT
    )


def _positive_money(value: object) -> Decimal:
    amount = _money(value)

    if amount < Decimal("0.00"):
        return Decimal("0.00")

    return amount


def _percentage(
    part: int,
    total: int,
) -> Decimal:
    if total <= 0:
        return Decimal("0.0")

    return (
        Decimal(part)
        * Decimal("100")
        / Decimal(total)
    ).quantize(
        PERCENT_QUANT
    )


def _user_label(user: object) -> str:
    if user is None:
        return "Система"

    full_name_method = getattr(
        user,
        "get_full_name",
        None,
    )

    full_name = (
        str(full_name_method() or "").strip()
        if callable(full_name_method)
        else ""
    )

    if full_name:
        return full_name

    for attribute in (
        "username",
        "email",
    ):
        value = str(
            getattr(
                user,
                attribute,
                "",
            )
            or ""
        ).strip()

        if value:
            return value

    return "Пользователь"


def _counterparty_label(
    invoice: Invoice,
) -> str:
    if invoice.counterparty_id:
        return invoice.counterparty.name

    return "Не назначен"


def _responsible_label(
    invoice: Invoice,
) -> str:
    if invoice.responsible_id:
        return invoice.responsible.full_name

    return "Не назначен"


def _invoice_queryset(
    invoices: QuerySet,
):
    if not isinstance(
        invoices,
        QuerySet,
    ):
        raise TypeError(
            "Enterprise analytics requires "
            "a Django QuerySet."
        )

    if invoices.model is not Invoice:
        raise TypeError(
            "Enterprise analytics requires "
            "an Invoice QuerySet."
        )

    return annotate_invoice_workspace(
        invoices
    )


def _presentation_items(
    invoices: QuerySet,
    *,
    today: date,
) -> tuple[dict[str, object], ...]:
    return tuple(
        build_presentations(
            list(
                _invoice_queryset(
                    invoices
                )
            ),
            today=today,
        )
    )


def _remaining_amount(
    item: Mapping[str, object],
) -> Decimal:
    payment = item["payment"]

    return _positive_money(
        payment["remaining_amount"]
    )


def _is_payment_candidate(
    item: Mapping[str, object],
) -> bool:
    invoice = item["invoice"]

    return bool(
        invoice.status
        in PAYMENT_CANDIDATE_STATUSES
        and _remaining_amount(item)
        > Decimal("0.00")
    )


def _needs_review(
    item: Mapping[str, object],
) -> bool:
    invoice = item["invoice"]
    document_readiness = item[
        "document_readiness"
    ]

    return bool(
        document_readiness.blockers
        or invoice.status
        in (
            Invoice.STATUS_NEW,
            Invoice.STATUS_IN_WORK,
            Invoice.STATUS_ON_APPROVAL,
        )
    )


def _metric(
    *,
    code: str,
    label: str,
    tone: str,
    filters: tuple[tuple[str, str], ...],
    items: Iterable[Mapping[str, object]],
) -> EnterpriseMetric:
    selected = tuple(items)

    return EnterpriseMetric(
        code=code,
        label=label,
        count=len(selected),
        amount=_money(
            sum(
                (
                    _remaining_amount(item)
                    for item in selected
                ),
                Decimal("0.00"),
            )
        ),
        tone=tone,
        filters=filters,
    )


def _dashboard_metrics(
    items: tuple[Mapping[str, object], ...],
) -> tuple[EnterpriseMetric, ...]:
    review_items = tuple(
        item
        for item in items
        if _needs_review(item)
    )

    due_today_items = tuple(
        item
        for item in items
        if item["is_due_today"]
    )

    overdue_items = tuple(
        item
        for item in items
        if item["is_overdue"]
    )

    ready_items = tuple(
        item
        for item in items
        if item["readiness_code"]
        == "ready"
    )

    return (
        _metric(
            code="needs_review",
            label="На проверке",
            tone="warning",
            filters=(
                (
                    "readiness",
                    "attention",
                ),
            ),
            items=review_items,
        ),
        _metric(
            code="due_today",
            label="К оплате сегодня",
            tone="accent",
            filters=(
                (
                    "payment_period",
                    "today",
                ),
            ),
            items=due_today_items,
        ),
        _metric(
            code="overdue",
            label="Просрочено",
            tone="danger",
            filters=(
                (
                    "readiness",
                    "overdue",
                ),
            ),
            items=overdue_items,
        ),
        _metric(
            code="ready",
            label="Готово к реестру",
            tone="success",
            filters=(
                (
                    "readiness",
                    "ready",
                ),
            ),
            items=ready_items,
        ),
    )


def _status_distribution(
    items: tuple[Mapping[str, object], ...],
) -> tuple[EnterpriseStatusSlice, ...]:
    total = len(items)
    slices = []

    for code, label in Invoice.STATUS_CHOICES:
        selected = tuple(
            item
            for item in items
            if item["invoice"].status
            == code
        )

        slices.append(
            EnterpriseStatusSlice(
                code=code,
                label=label,
                count=len(selected),
                document_amount=_money(
                    sum(
                        (
                            _money(
                                item[
                                    "invoice"
                                ].amount
                            )
                            for item in selected
                        ),
                        Decimal("0.00"),
                    )
                ),
                outstanding_amount=_money(
                    sum(
                        (
                            _remaining_amount(item)
                            for item in selected
                        ),
                        Decimal("0.00"),
                    )
                ),
                share_percent=_percentage(
                    len(selected),
                    total,
                ),
            )
        )

    return tuple(slices)


def _payment_series(
    items: tuple[Mapping[str, object], ...],
    *,
    period_start: date,
    period_days: int,
) -> tuple[EnterprisePaymentPoint, ...]:
    if period_days <= 0:
        raise ValueError(
            "period_days must be positive."
        )

    points = []

    for offset in range(period_days):
        day = (
            period_start
            + timedelta(days=offset)
        )

        selected = tuple(
            item
            for item in items
            if _is_payment_candidate(item)
            and item["invoice"].planned_payment_date
            == day
        )

        points.append(
            EnterprisePaymentPoint(
                day=day,
                label=day.strftime(
                    "%d.%m"
                ),
                count=len(selected),
                amount=_money(
                    sum(
                        (
                            _remaining_amount(item)
                            for item in selected
                        ),
                        Decimal("0.00"),
                    )
                ),
                bucket=(
                    "today"
                    if offset == 0
                    else "upcoming"
                ),
            )
        )

    return tuple(points)


def _largest_payments(
    items: tuple[Mapping[str, object], ...],
    *,
    period_start: date,
    period_days: int,
    limit: int,
) -> tuple[EnterprisePaymentItem, ...]:
    if limit < 0:
        raise ValueError(
            "limit cannot be negative."
        )

    period_end = (
        period_start
        + timedelta(
            days=period_days - 1
        )
    )

    selected = [
        item
        for item in items
        if _is_payment_candidate(item)
        and item[
            "invoice"
        ].planned_payment_date
        and period_start
        <= item[
            "invoice"
        ].planned_payment_date
        <= period_end
    ]

    selected.sort(
        key=lambda item: (
            -_remaining_amount(item),
            item[
                "invoice"
            ].planned_payment_date,
            item["invoice"].id,
        )
    )

    return tuple(
        EnterprisePaymentItem(
            invoice_id=item["invoice"].id,
            title=item["title"],
            counterparty_label=(
                _counterparty_label(
                    item["invoice"]
                )
            ),
            planned_payment_date=(
                item[
                    "invoice"
                ].planned_payment_date
            ),
            remaining_amount=(
                _remaining_amount(item)
            ),
            readiness_code=item[
                "readiness_code"
            ],
            readiness_label=item[
                "readiness_label"
            ],
        )
        for item in selected[:limit]
    )


def _task_items(
    items: tuple[Mapping[str, object], ...],
    *,
    limit: int,
    responsible_id: int | None,
) -> tuple[EnterpriseTaskItem, ...]:
    if limit < 0:
        raise ValueError(
            "limit cannot be negative."
        )

    selected = [
        item
        for item in items
        if (
            _needs_review(item)
            or item["is_overdue"]
        )
        and (
            responsible_id is None
            or item[
                "invoice"
            ].responsible_id
            == responsible_id
        )
    ]

    selected.sort(
        key=lambda item: (
            item["urgency_rank"],
            (
                item[
                    "invoice"
                ].planned_payment_date
                or date.max
            ),
            -item["invoice"].id,
        )
    )

    return tuple(
        EnterpriseTaskItem(
            invoice_id=item["invoice"].id,
            title=item["title"],
            counterparty_label=(
                _counterparty_label(
                    item["invoice"]
                )
            ),
            responsible_label=(
                _responsible_label(
                    item["invoice"]
                )
            ),
            planned_payment_date=(
                item[
                    "invoice"
                ].planned_payment_date
            ),
            amount=_money(
                item["invoice"].amount
            ),
            remaining_amount=(
                _remaining_amount(item)
            ),
            readiness_code=item[
                "readiness_code"
            ],
            readiness_label=item[
                "readiness_label"
            ],
            readiness_tone=item[
                "readiness_tone"
            ],
            reason=item["reason"],
            next_action=item["next_action"],
            urgency_rank=item[
                "urgency_rank"
            ],
        )
        for item in selected[:limit]
    )


def _recent_actions(
    items: tuple[Mapping[str, object], ...],
    *,
    limit: int,
) -> tuple[EnterpriseActivityItem, ...]:
    if limit < 0:
        raise ValueError(
            "limit cannot be negative."
        )

    if limit == 0 or not items:
        return ()

    item_by_invoice_id = {
        item["invoice"].id: item
        for item in items
    }

    logs = (
        InvoiceLog.objects
        .filter(
            invoice_id__in=(
                item_by_invoice_id.keys()
            )
        )
        .select_related(
            "invoice",
            "user",
        )
        .order_by(
            "-created_at",
            "-id",
        )[:limit]
    )

    return tuple(
        EnterpriseActivityItem(
            log_id=log.id,
            invoice_id=log.invoice_id,
            title=(
                item_by_invoice_id[
                    log.invoice_id
                ]["title"]
            ),
            action=(
                humanize_invoice_log_action(
                    log.action
                )
            ),
            actor_label=_user_label(
                log.user
            ),
            created_at=log.created_at,
        )
        for log in logs
    )


def build_enterprise_dashboard_analytics(
    invoices: QuerySet,
    *,
    today: date | None = None,
    series_days: int = 7,
    task_limit: int = 5,
    recent_activity_limit: int = 5,
    largest_payment_limit: int = 5,
    task_responsible_id: int | None = None,
) -> EnterpriseDashboardAnalytics:
    resolved_today = (
        today
        or timezone.localdate()
    )

    items = _presentation_items(
        invoices,
        today=resolved_today,
    )

    return EnterpriseDashboardAnalytics(
        metrics=_dashboard_metrics(
            items
        ),
        status_distribution=(
            _status_distribution(
                items
            )
        ),
        payment_series=_payment_series(
            items,
            period_start=resolved_today,
            period_days=series_days,
        ),
        tasks=_task_items(
            items,
            limit=task_limit,
            responsible_id=(
                task_responsible_id
            ),
        ),
        recent_actions=_recent_actions(
            items,
            limit=recent_activity_limit,
        ),
        largest_payments=(
            _largest_payments(
                items,
                period_start=(
                    resolved_today
                ),
                period_days=series_days,
                limit=(
                    largest_payment_limit
                ),
            )
        ),
        total_documents=len(items),
        total_document_amount=_money(
            sum(
                (
                    _money(
                        item[
                            "invoice"
                        ].amount
                    )
                    for item in items
                ),
                Decimal("0.00"),
            )
        ),
        total_outstanding_amount=_money(
            sum(
                (
                    _remaining_amount(item)
                    for item in items
                ),
                Decimal("0.00"),
            )
        ),
        task_scope=(
            "responsible"
            if task_responsible_id
            is not None
            else "visible"
        ),
    )


def build_enterprise_payment_schedule_analytics(
    invoices: QuerySet,
    *,
    today: date | None = None,
    period_start: date | None = None,
    period_days: int = 7,
    largest_payment_limit: int = 5,
) -> EnterprisePaymentScheduleAnalytics:
    resolved_today = (
        today
        or timezone.localdate()
    )

    resolved_period_start = (
        period_start
        or resolved_today
    )

    items = _presentation_items(
        invoices,
        today=resolved_today,
    )

    candidates = tuple(
        item
        for item in items
        if _is_payment_candidate(item)
    )

    week_end = (
        resolved_today
        + timedelta(
            days=6
        )
    )

    metrics = (
        _metric(
            code="total",
            label="Всего к оплате",
            tone="neutral",
            filters=(),
            items=candidates,
        ),
        _metric(
            code="today",
            label="Сегодня",
            tone="accent",
            filters=(
                (
                    "filter",
                    "today",
                ),
            ),
            items=(
                item
                for item in candidates
                if item[
                    "invoice"
                ].planned_payment_date
                == resolved_today
            ),
        ),
        _metric(
            code="week",
            label="Неделя",
            tone="info",
            filters=(
                (
                    "filter",
                    "week",
                ),
            ),
            items=(
                item
                for item in candidates
                if item[
                    "invoice"
                ].planned_payment_date
                and resolved_today
                <= item[
                    "invoice"
                ].planned_payment_date
                <= week_end
            ),
        ),
        _metric(
            code="overdue",
            label="Просрочено",
            tone="danger",
            filters=(
                (
                    "filter",
                    "overdue",
                ),
            ),
            items=(
                item
                for item in candidates
                if item[
                    "invoice"
                ].planned_payment_date
                and item[
                    "invoice"
                ].planned_payment_date
                < resolved_today
            ),
        ),
        _metric(
            code="no_date",
            label="Без даты",
            tone="warning",
            filters=(
                (
                    "filter",
                    "no_date",
                ),
            ),
            items=(
                item
                for item in candidates
                if item[
                    "invoice"
                ].planned_payment_date
                is None
            ),
        ),
    )

    return (
        EnterprisePaymentScheduleAnalytics(
            metrics=metrics,
            payment_series=(
                _payment_series(
                    items,
                    period_start=(
                        resolved_period_start
                    ),
                    period_days=period_days,
                )
            ),
            largest_payments=(
                _largest_payments(
                    items,
                    period_start=(
                        resolved_period_start
                    ),
                    period_days=period_days,
                    limit=(
                        largest_payment_limit
                    ),
                )
            ),
            period_start=resolved_period_start,
            period_end=(
                resolved_period_start
                + timedelta(
                    days=period_days - 1
                )
            ),
        )
    )


def build_enterprise_upload_journal_analytics(
    batches: QuerySet,
    *,
    recent_limit: int = 10,
) -> EnterpriseUploadJournalAnalytics:
    if not isinstance(
        batches,
        QuerySet,
    ):
        raise TypeError(
            "Upload analytics requires "
            "a Django QuerySet."
        )

    if batches.model is not InvoiceUploadBatch:
        raise TypeError(
            "Upload analytics requires "
            "an InvoiceUploadBatch QuerySet."
        )

    if recent_limit < 0:
        raise ValueError(
            "recent_limit cannot be negative."
        )

    batch_items = tuple(
        batches
        .select_related(
            "user"
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    total_files = sum(
        batch.total_files
        for batch in batch_items
    )

    uploaded_files = sum(
        batch.uploaded_count
        for batch in batch_items
    )

    return EnterpriseUploadJournalAnalytics(
        total_batches=len(batch_items),
        completed_batches=sum(
            1
            for batch in batch_items
            if batch.status
            == InvoiceUploadBatch.STATUS_COMPLETED
        ),
        partial_batches=sum(
            1
            for batch in batch_items
            if batch.status
            == InvoiceUploadBatch.STATUS_PARTIAL
        ),
        empty_batches=sum(
            1
            for batch in batch_items
            if batch.status
            == InvoiceUploadBatch.STATUS_EMPTY
        ),
        total_files=total_files,
        uploaded_files=uploaded_files,
        duplicate_files=sum(
            batch.duplicate_count
            for batch in batch_items
        ),
        skipped_files=sum(
            batch.skipped_count
            for batch in batch_items
        ),
        success_rate=(
            (
                Decimal(uploaded_files)
                * Decimal("100")
                / Decimal(total_files)
            ).quantize(
                PERCENT_QUANT
            )
            if total_files
            else Decimal("0.0")
        ),
        recent_batches=tuple(
            EnterpriseUploadBatchItem(
                batch_id=batch.id,
                created_at=batch.created_at,
                user_label=_user_label(
                    batch.user
                ),
                status_code=batch.status,
                status_label=(
                    batch.get_status_display()
                ),
                total_files=(
                    batch.total_files
                ),
                uploaded_count=(
                    batch.uploaded_count
                ),
                duplicate_count=(
                    batch.duplicate_count
                ),
                skipped_count=(
                    batch.skipped_count
                ),
            )
            for batch in batch_items[
                :recent_limit
            ]
        ),
    )


def _registry_item_title(
    item: PaymentRegistryItem,
) -> str:
    invoice = item.invoice
    number = str(
        invoice.invoice_number
        or ""
    ).strip()

    if number:
        return (
            invoice.get_document_type_display()
            + " №"
            + number
        )

    return (
        invoice.get_document_type_display()
        + " без номера"
    )


def build_enterprise_registry_analytics(
    registry: PaymentRegistry,
    *,
    items: Iterable[
        PaymentRegistryItem
    ] | None = None,
    check_result: Mapping[
        str,
        object,
    ] | None = None,
) -> EnterpriseRegistryAnalytics:
    if items is None:
        items = (
            registry.items
            .select_related(
                "invoice",
                "invoice__counterparty",
            )
            .exclude(
                status=(
                    PaymentRegistryItem
                    .STATUS_CANCELLED
                )
            )
            .order_by(
                "planned_payment_date",
                "invoice_id",
            )
        )

    active_items = tuple(
        item
        for item in items
        if item.status
        != PaymentRegistryItem.STATUS_CANCELLED
    )

    calculated_total = _money(
        sum(
            (
                _money(item.amount)
                for item in active_items
            ),
            Decimal("0.00"),
        )
    )

    lifecycle_codes = [
        code
        for code, _label
        in REGISTRY_LIFECYCLE
    ]

    try:
        current_position = (
            lifecycle_codes.index(
                registry.status
            )
        )
    except ValueError:
        current_position = -1

    lifecycle = tuple(
        EnterpriseRegistryLifecycleStep(
            code=code,
            label=label,
            position=position,
            is_complete=bool(
                current_position >= 0
                and position
                < current_position
            ),
            is_current=bool(
                position
                == current_position
            ),
        )
        for position, (
            code,
            label,
        ) in enumerate(
            REGISTRY_LIFECYCLE
        )
    )

    status_distribution = tuple(
        EnterpriseRegistryStatusSlice(
            code=code,
            label=label,
            count=sum(
                1
                for item in active_items
                if item.status == code
            ),
            amount=_money(
                sum(
                    (
                        _money(item.amount)
                        for item in active_items
                        if item.status == code
                    ),
                    Decimal("0.00"),
                )
            ),
        )
        for code, label
        in PaymentRegistryItem.STATUS_CHOICES
        if code
        != PaymentRegistryItem.STATUS_CANCELLED
    )

    item_by_invoice_id = {
        item.invoice_id: item
        for item in active_items
    }

    raw_errors = (
        tuple(
            check_result.get(
                "errors",
                (),
            )
        )
        if check_result is not None
        else ()
    )

    issues = []

    for error in raw_errors:
        invoice_id = int(
            error.get(
                "invoice_id",
                0,
            )
            or 0
        )

        item = item_by_invoice_id.get(
            invoice_id
        )

        title = (
            _registry_item_title(item)
            if item is not None
            else "Документ"
        )

        issues.append(
            EnterpriseRegistryIssue(
                invoice_id=invoice_id,
                title=title,
                messages=tuple(
                    str(message)
                    for message in error.get(
                        "messages",
                        (),
                    )
                ),
            )
        )

    check_available = (
        check_result is not None
    )

    ready_count = (
        int(
            check_result.get(
                "ready_count",
                0,
            )
            or 0
        )
        if check_available
        else 0
    )

    errors_count = (
        int(
            check_result.get(
                "errors_count",
                0,
            )
            or 0
        )
        if check_available
        else 0
    )

    warnings_count = (
        int(
            check_result.get(
                "warnings_count",
                0,
            )
            or 0
        )
        if check_available
        else 0
    )

    return EnterpriseRegistryAnalytics(
        registry_id=registry.id,
        status_code=registry.status,
        status_label=(
            registry.get_status_display()
        ),
        lifecycle=lifecycle,
        item_count=len(active_items),
        stored_item_count=(
            registry.items_count
        ),
        calculated_total_amount=(
            calculated_total
        ),
        stored_total_amount=_money(
            registry.total_amount
        ),
        is_item_count_consistent=bool(
            registry.items_count
            == len(active_items)
        ),
        is_total_amount_consistent=bool(
            _money(
                registry.total_amount
            )
            == calculated_total
        ),
        ready_count=ready_count,
        blocked_count=(
            max(
                len(active_items)
                - ready_count,
                0,
            )
            if check_available
            else 0
        ),
        errors_count=errors_count,
        warnings_count=warnings_count,
        check_available=check_available,
        status_distribution=(
            status_distribution
        ),
        issues=tuple(issues),
    )


def enterprise_analytics_to_primitive(
    value: object,
) -> object:
    if is_dataclass(value):
        return (
            enterprise_analytics_to_primitive(
                asdict(value)
            )
        )

    if isinstance(value, Mapping):
        return {
            str(key): (
                enterprise_analytics_to_primitive(
                    item
                )
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):
        return [
            enterprise_analytics_to_primitive(
                item
            )
            for item in value
        ]

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    return value
