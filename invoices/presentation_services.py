from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db.models import (
    DecimalField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    Invoice,
    InvoicePayment,
    PaymentRegistry,
    PaymentRegistryItem,
)
from .readiness_services import (
    evaluate_document_readiness,
    evaluate_payment_readiness,
)


ACTIVE_REGISTRY_STATUSES = (
    PaymentRegistry.STATUS_DRAFT,
    PaymentRegistry.STATUS_CHECKED,
    PaymentRegistry.STATUS_EXPORTED,
    PaymentRegistry.STATUS_PARTIALLY_PAID,
)

READINESS_FILTER_CHOICES = (
    ("", "Все состояния"),
    ("attention", "Требуют внимания"),
    ("ready", "Готовы к реестру"),
    ("overdue", "Просрочены"),
    ("in_registry", "Уже в реестре"),
)


def annotate_invoice_workspace(queryset):
    active_registry_items = (
        PaymentRegistryItem.objects
        .filter(
            invoice_id=OuterRef("pk"),
            registry__status__in=ACTIVE_REGISTRY_STATUSES,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED,
        )
        .order_by("id")
    )

    return (
        queryset
        .select_related(
            "user",
            "counterparty",
            "responsible",
        )
        .annotate(
            payment_paid_sum=Coalesce(
                Sum(
                    "payments__amount",
                    filter=Q(
                        payments__status=InvoicePayment.STATUS_POSTED,
                    ),
                ),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(
                        max_digits=12,
                        decimal_places=2,
                    ),
                ),
            ),
            active_registry_id=Subquery(
                active_registry_items.values("registry_id")[:1],
            ),
        )
    )


def _decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


def _date_label(value: object) -> str:
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value or "").strip()


def _document_identity(invoice: Invoice) -> tuple[str, str]:
    type_label = invoice.get_document_type_display()
    number = str(invoice.invoice_number or "").strip()
    document_date = invoice.document_date or invoice.invoice_date
    document_date_label = _date_label(document_date)

    if number:
        title = f"{type_label} №{number}"
    else:
        title = f"{type_label} #{invoice.id}"

    meta_parts = []
    if document_date_label:
        meta_parts.append(f"от {document_date_label}")
    if invoice.title and invoice.title.strip() != title:
        meta_parts.append(invoice.title.strip())

    return title, " · ".join(meta_parts)


def payment_summary_from_invoice(invoice: Invoice) -> dict[str, object]:
    invoice_amount = _decimal(invoice.amount)
    paid_amount = _decimal(
        getattr(invoice, "payment_paid_sum", Decimal("0.00"))
    )
    remaining_amount = invoice_amount - paid_amount

    if invoice_amount <= Decimal("0.00"):
        status = "no_amount"
        status_label = "Сумма не указана"
    elif paid_amount <= Decimal("0.00"):
        status = "unpaid"
        status_label = "Не оплачен"
    elif paid_amount < invoice_amount:
        status = "partial"
        status_label = "Частично оплачен"
    elif paid_amount == invoice_amount:
        status = "paid"
        status_label = "Оплачен"
    else:
        status = "overpaid"
        status_label = "Переплата"

    return {
        "invoice_amount": invoice_amount,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount,
        "payment_status": status,
        "payment_status_label": status_label,
    }


def build_invoice_presentation(
    invoice: Invoice,
    *,
    today: date | None = None,
) -> dict[str, object]:
    today = today or timezone.localdate()
    payment = payment_summary_from_invoice(invoice)
    document_readiness = evaluate_document_readiness(invoice)
    payment_readiness = evaluate_payment_readiness(
        invoice,
        active_registry_id=getattr(invoice, "active_registry_id", None),
        payment_summary=payment,
    )
    title, meta = _document_identity(invoice)

    planned_date = invoice.planned_payment_date
    remaining_amount = payment["remaining_amount"]
    is_overdue = bool(
        planned_date
        and planned_date < today
        and remaining_amount > Decimal("0.00")
    )
    is_due_today = bool(
        planned_date == today
        and remaining_amount > Decimal("0.00")
    )

    if invoice.status == Invoice.STATUS_PAID or (
        invoice.amount
        and remaining_amount <= Decimal("0.00")
    ):
        readiness_code = "paid"
        readiness_label = "Оплачен"
        readiness_tone = "success"
        reason = "Обязательство по документу закрыто."
        next_action = "Просмотреть оплату"
        urgency_rank = 90
    elif document_readiness.is_legacy_repair:
        readiness_code = "repair"
        readiness_label = "Требуется исправление"
        readiness_tone = "danger"
        reason = document_readiness.primary_blocker.message
        next_action = document_readiness.next_action
        urgency_rank = 0
    elif document_readiness.blockers:
        readiness_code = "attention"
        readiness_label = "Нужна проверка"
        readiness_tone = "warning"
        reason = document_readiness.primary_blocker.message
        next_action = document_readiness.next_action
        urgency_rank = 20
    elif getattr(invoice, "active_registry_id", None):
        readiness_code = "in_registry"
        readiness_label = "В реестре"
        readiness_tone = "info"
        reason = f"Добавлен в реестр №{invoice.active_registry_id}."
        next_action = "Открыть документ"
        urgency_rank = 70
    elif is_overdue:
        readiness_code = "overdue"
        readiness_label = "Просрочен"
        readiness_tone = "danger"
        reason = "Плановая дата оплаты уже прошла."
        next_action = "Проверить оплату"
        urgency_rank = 10
    elif invoice.status == Invoice.STATUS_APPROVED:
        if payment_readiness.can_add_to_registry:
            readiness_code = "ready"
            readiness_label = "Готов к реестру"
            readiness_tone = "success"
            reason = "Все обязательные данные заполнены."
            next_action = payment_readiness.next_action
            urgency_rank = 60
        else:
            readiness_code = "payment_blocked"
            readiness_label = "Не готов к оплате"
            readiness_tone = "warning"
            reason = payment_readiness.primary_blocker.message
            next_action = payment_readiness.next_action
            urgency_rank = 15
    elif invoice.status == Invoice.STATUS_ON_APPROVAL:
        readiness_code = "approval"
        readiness_label = "На согласовании"
        readiness_tone = "info"
        reason = "Документ готов к решению согласующего."
        next_action = document_readiness.next_action
        urgency_rank = 30
    elif invoice.status == Invoice.STATUS_IN_WORK:
        readiness_code = "in_work"
        readiness_label = "В работе"
        readiness_tone = "info"
        reason = "Документ обрабатывается ответственным."
        next_action = document_readiness.next_action
        urgency_rank = 35
    elif invoice.status == Invoice.STATUS_NEW:
        readiness_code = "new"
        readiness_label = "Новый"
        readiness_tone = "neutral"
        reason = "Документ ещё не принят в работу."
        next_action = document_readiness.next_action
        urgency_rank = 40
    else:
        readiness_code = invoice.status
        readiness_label = invoice.get_status_display()
        readiness_tone = "neutral"
        reason = "Проверьте состояние документа."
        next_action = document_readiness.next_action
        urgency_rank = 50

    warning_messages = document_readiness.warning_messages
    requires_attention = bool(
        document_readiness.blockers
        or is_overdue
        or (
            invoice.status == Invoice.STATUS_APPROVED
            and not payment_readiness.can_add_to_registry
            and not getattr(invoice, "active_registry_id", None)
            and payment["remaining_amount"] > Decimal("0.00")
        )
    )

    presentation = {
        "invoice": invoice,
        "title": title,
        "meta": meta,
        "document_date_label": _date_label(
            invoice.document_date or invoice.invoice_date
        ) or "Не указана",
        "planned_payment_date_label": _date_label(
            invoice.planned_payment_date
        ) or "Не назначена",
        "status_label": invoice.get_status_display(),
        "readiness_code": readiness_code,
        "readiness_label": readiness_label,
        "readiness_tone": readiness_tone,
        "reason": reason,
        "next_action": next_action,
        "urgency_rank": urgency_rank,
        "requires_attention": requires_attention,
        "is_overdue": is_overdue,
        "is_due_today": is_due_today,
        "payment": payment,
        "document_readiness": document_readiness,
        "payment_readiness": payment_readiness,
        "warning_messages": warning_messages,
    }
    invoice.production = presentation
    return presentation


def build_presentations(
    invoices: Iterable[Invoice],
    *,
    today: date | None = None,
) -> list[dict[str, object]]:
    today = today or timezone.localdate()
    return [
        build_invoice_presentation(invoice, today=today)
        for invoice in invoices
    ]


def build_dashboard_workspace(
    invoices: Iterable[Invoice],
    *,
    today: date | None = None,
) -> dict[str, object]:
    today = today or timezone.localdate()
    items = build_presentations(invoices, today=today)
    month_start = today.replace(day=1)

    attention = [
        item
        for item in items
        if item["requires_attention"]
        or item["invoice"].status in (
            Invoice.STATUS_NEW,
            Invoice.STATUS_IN_WORK,
            Invoice.STATUS_ON_APPROVAL,
        )
    ]
    attention.sort(
        key=lambda item: (
            item["urgency_rank"],
            item["invoice"].planned_payment_date or date.max,
            -item["invoice"].id,
        )
    )

    upcoming = [
        item
        for item in items
        if item["invoice"].planned_payment_date
        and item["invoice"].planned_payment_date >= today
        and item["payment"]["remaining_amount"] > Decimal("0.00")
        and item["invoice"].status != Invoice.STATUS_PAID
    ]
    upcoming.sort(
        key=lambda item: (
            item["invoice"].planned_payment_date,
            item["urgency_rank"],
            item["invoice"].id,
        )
    )

    latest = sorted(
        items,
        key=lambda item: (
            item["invoice"].created_at,
            item["invoice"].id,
        ),
        reverse=True,
    )

    return {
        "total_count": len(items),
        "attention_count": sum(
            1 for item in items if item["requires_attention"]
        ),
        "due_today_count": sum(
            1 for item in items if item["is_due_today"]
        ),
        "overdue_count": sum(
            1 for item in items if item["is_overdue"]
        ),
        "ready_count": sum(
            1 for item in items
            if item["readiness_code"] == "ready"
        ),
        "paid_month_count": sum(
            1 for item in items
            if item["invoice"].paid_at
            and item["invoice"].paid_at >= month_start
        ),
        "attention_documents": attention[:6],
        "upcoming_payments": upcoming[:5],
        "latest_documents": latest[:5],
    }
