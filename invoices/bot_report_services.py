import json
from pathlib import Path

from django.conf import settings
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from invoices.models import (
    Invoice,
    PaymentRegistryItem,
)
from invoices.payment_registry_services import (
    ACTIVE_REGISTRY_STATUSES,
    validate_invoice_for_payment_registry,
)


INVOICE_BOT_REPORT_PATH = (
    Path("var")
    / "invoice_bot"
    / "latest_report.json"
)

BOT_REPORT_CATEGORY_READY = "ready"
BOT_REPORT_CATEGORY_NOT_READY = "not-ready"
BOT_REPORT_CATEGORY_WITHOUT_PLANNED_PAYMENT_DATE = (
    "without-planned-payment-date"
)
BOT_REPORT_CATEGORY_WITHOUT_COUNTERPARTY = "without-counterparty"
BOT_REPORT_CATEGORY_UNVERIFIED_AMOUNT = "unverified-amount"
BOT_REPORT_CATEGORY_WITHOUT_OCR_TEXT = "without-ocr-text"
BOT_REPORT_CATEGORY_UNKNOWN_DOCUMENT_TYPE = "unknown-document-type"

INVOICE_BOT_REPORT_CATEGORIES = {
    BOT_REPORT_CATEGORY_READY: {
        "title": "Готовы к реестру",
        "description": (
            "Документы, которые проходят проверку готовности "
            "к добавлению в реестр оплаты."
        ),
    },
    BOT_REPORT_CATEGORY_NOT_READY: {
        "title": "Не готовы к реестру",
        "description": (
            "Документы, по которым есть блокирующие причины "
            "перед добавлением в реестр оплаты."
        ),
    },
    BOT_REPORT_CATEGORY_WITHOUT_PLANNED_PAYMENT_DATE: {
        "title": "Без даты оплаты",
        "description": "Документы без плановой даты оплаты.",
    },
    BOT_REPORT_CATEGORY_WITHOUT_COUNTERPARTY: {
        "title": "Без контрагента",
        "description": (
            "Документы, к которым не привязан контрагент."
        ),
    },
    BOT_REPORT_CATEGORY_UNVERIFIED_AMOUNT: {
        "title": "Сумма не подтверждена",
        "description": (
            "Документы, по которым сумма требует ручной проверки."
        ),
    },
    BOT_REPORT_CATEGORY_WITHOUT_OCR_TEXT: {
        "title": "Без OCR-текста",
        "description": (
            "Документы, у которых нет сохранённого OCR-текста."
        ),
    },
    BOT_REPORT_CATEGORY_UNKNOWN_DOCUMENT_TYPE: {
        "title": "Неизвестный тип документа",
        "description": (
            "Документы, у которых OCR-текст есть, "
            "но тип документа не распознан."
        ),
    },
}

REPORT_COUNT_FIELDS = (
    "total_count",
    "without_planned_payment_date_count",
    "without_counterparty_count",
    "unverified_amount_count",
    "without_ocr_text_count",
    "unknown_document_type_count",
    "ready_for_registry_count",
    "not_ready_for_registry_count",
    "without_vendor_count",
    "counterparty_action_required_count",
    "waiting_1c_sync_count",
)


def get_invoice_bot_report_path():
    return (
        Path(settings.BASE_DIR)
        / INVOICE_BOT_REPORT_PATH
    )


def read_latest_invoice_bot_report():
    report_path = get_invoice_bot_report_path()

    if not report_path.exists():
        return None

    try:
        report = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    if not isinstance(
        report,
        dict,
    ):
        return None

    for field_name in REPORT_COUNT_FIELDS:
        report[field_name] = _safe_int(
            report.get(
                field_name
            )
        )

    generated_at = report.get(
        "generated_at"
    )

    report["generated_at_datetime"] = None

    if generated_at:
        report["generated_at_datetime"] = parse_datetime(
            generated_at
        )

    return report


def build_live_invoice_bot_report():
    counters = {
        field_name: 0
        for field_name in REPORT_COUNT_FIELDS
    }

    for invoice in _get_base_invoice_queryset():
        counters["total_count"] += 1

        if not invoice.planned_payment_date:
            counters[
                "without_planned_payment_date_count"
            ] += 1

        if not invoice.vendor:
            counters["without_vendor_count"] += 1

        if not invoice.counterparty_id:
            counters["without_counterparty_count"] += 1

            if (
                invoice.counterparty_match_status
                == Invoice.COUNTERPARTY_MATCH_NOT_FOUND
            ):
                counters["waiting_1c_sync_count"] += 1
            else:
                counters[
                    "counterparty_action_required_count"
                ] += 1

        if not invoice.amount_verified:
            counters["unverified_amount_count"] += 1

        has_ocr_text = bool(
            invoice.ocr_text
        )

        if not has_ocr_text:
            counters["without_ocr_text_count"] += 1

        if (
            has_ocr_text
            and invoice.document_type
            == Invoice.DOCUMENT_TYPE_UNKNOWN
        ):
            counters[
                "unknown_document_type_count"
            ] += 1

        errors, warnings = (
            validate_invoice_for_payment_registry(
                invoice
            )
        )

        if errors:
            counters[
                "not_ready_for_registry_count"
            ] += 1
        else:
            counters[
                "ready_for_registry_count"
            ] += 1

    technical_audit = {
        "without_ocr_text_count": counters[
            "without_ocr_text_count"
        ],
        "unknown_document_type_count": counters[
            "unknown_document_type_count"
        ],
        "without_vendor_count": counters[
            "without_vendor_count"
        ],
        "without_counterparty_count": counters[
            "without_counterparty_count"
        ],
        "counterparty_action_required_count": counters[
            "counterparty_action_required_count"
        ],
        "waiting_1c_sync_count": counters[
            "waiting_1c_sync_count"
        ],
    }

    user_work_queue = {
        "without_planned_payment_date_count": counters[
            "without_planned_payment_date_count"
        ],
        "unverified_amount_count": counters[
            "unverified_amount_count"
        ],
        "ready_for_registry_count": counters[
            "ready_for_registry_count"
        ],
        "not_ready_for_registry_count": counters[
            "not_ready_for_registry_count"
        ],
    }

    return {
        "report_version": 2,
        "generated_at": timezone.now().isoformat(),
        **counters,
        "technical_audit": technical_audit,
        "user_work_queue": user_work_queue,
        "mode": "live",
    }


def get_dashboard_invoice_bot_report():
    snapshot = read_latest_invoice_bot_report()

    if snapshot is None:
        return None

    live_report = build_live_invoice_bot_report()

    live_report["snapshot_generated_at"] = snapshot.get(
        "generated_at"
    )
    live_report["snapshot_generated_at_datetime"] = snapshot.get(
        "generated_at_datetime"
    )

    return live_report


def get_invoice_bot_report_category(category):
    return INVOICE_BOT_REPORT_CATEGORIES.get(
        category
    )


def get_invoice_bot_report_items(category):
    category_data = get_invoice_bot_report_category(
        category
    )

    if category_data is None:
        return None, []

    invoices = _get_base_invoice_queryset()
    invoices = _apply_category_filter(
        invoices,
        category,
    )

    items = []

    for invoice in invoices:
        errors, warnings = (
            validate_invoice_for_payment_registry(
                invoice
            )
        )

        if (
            category == BOT_REPORT_CATEGORY_READY
            and errors
        ):
            continue

        if (
            category == BOT_REPORT_CATEGORY_NOT_READY
            and not errors
        ):
            continue

        items.append(
            {
                "invoice": invoice,
                "errors": errors,
                "warnings": warnings,
            }
        )

    return category_data, items


def _get_base_invoice_queryset():
    active_registry_items = (
        PaymentRegistryItem.objects
        .filter(
            invoice_id=OuterRef(
                "pk"
            ),
            registry__status__in=ACTIVE_REGISTRY_STATUSES,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            "id"
        )
    )

    return (
        Invoice.objects
        .select_related(
            "counterparty",
            "responsible",
            "user",
        )
        .annotate(
            active_registry_id=Subquery(
                active_registry_items.values(
                    "registry_id"
                )[:1]
            )
        )
        .filter(
            is_deleted=False,
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )


def _apply_category_filter(invoices, category):
    if category in (
        BOT_REPORT_CATEGORY_READY,
        BOT_REPORT_CATEGORY_NOT_READY,
    ):
        return invoices

    if category == BOT_REPORT_CATEGORY_WITHOUT_PLANNED_PAYMENT_DATE:
        return invoices.filter(
            planned_payment_date__isnull=True,
        )

    if category == BOT_REPORT_CATEGORY_WITHOUT_COUNTERPARTY:
        return invoices.filter(
            counterparty__isnull=True,
        )

    if category == BOT_REPORT_CATEGORY_UNVERIFIED_AMOUNT:
        return invoices.filter(
            amount_verified=False,
        )

    if category == BOT_REPORT_CATEGORY_WITHOUT_OCR_TEXT:
        return invoices.filter(
            Q(ocr_text__isnull=True)
            |
            Q(ocr_text="")
        )

    if category == BOT_REPORT_CATEGORY_UNKNOWN_DOCUMENT_TYPE:
        return (
            invoices
            .filter(
                document_type=Invoice.DOCUMENT_TYPE_UNKNOWN,
            )
            .exclude(
                Q(ocr_text__isnull=True)
                |
                Q(ocr_text="")
            )
        )

    return invoices.none()


def _safe_int(value):
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0

