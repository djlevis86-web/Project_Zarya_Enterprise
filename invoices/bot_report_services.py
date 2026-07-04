import json
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils.dateparse import parse_datetime

from invoices.models import Invoice
from invoices.payment_registry_services import validate_invoice_for_payment_registry


INVOICE_BOT_REPORT_PATH = (
    Path("var")
    / "invoice_bot"
    / "latest_report.json"
)

BOT_REPORT_CATEGORY_READY = "ready"
BOT_REPORT_CATEGORY_NOT_READY = "not-ready"
BOT_REPORT_CATEGORY_WITHOUT_PLANNED_PAYMENT_DATE = "without-planned-payment-date"
BOT_REPORT_CATEGORY_WITHOUT_COUNTERPARTY = "without-counterparty"
BOT_REPORT_CATEGORY_UNVERIFIED_AMOUNT = "unverified-amount"
BOT_REPORT_CATEGORY_WITHOUT_OCR_TEXT = "without-ocr-text"
BOT_REPORT_CATEGORY_UNKNOWN_DOCUMENT_TYPE = "unknown-document-type"

INVOICE_BOT_REPORT_CATEGORIES = {
    BOT_REPORT_CATEGORY_READY: {
        "title": "Готовы к реестру",
        "description": "Счета, которые проходят проверку готовности к добавлению в реестр оплаты.",
    },
    BOT_REPORT_CATEGORY_NOT_READY: {
        "title": "Не готовы к реестру",
        "description": "Счета, по которым есть блокирующие причины перед добавлением в реестр оплаты.",
    },
    BOT_REPORT_CATEGORY_WITHOUT_PLANNED_PAYMENT_DATE: {
        "title": "Без даты оплаты",
        "description": "Счета без плановой даты оплаты.",
    },
    BOT_REPORT_CATEGORY_WITHOUT_COUNTERPARTY: {
        "title": "Без контрагента",
        "description": "Счета, к которым не привязан контрагент.",
    },
    BOT_REPORT_CATEGORY_UNVERIFIED_AMOUNT: {
        "title": "Сумма не подтверждена",
        "description": "Счета, по которым сумма требует ручной проверки.",
    },
    BOT_REPORT_CATEGORY_WITHOUT_OCR_TEXT: {
        "title": "Без OCR-текста",
        "description": "Счета, у которых нет сохранённого OCR-текста.",
    },
    BOT_REPORT_CATEGORY_UNKNOWN_DOCUMENT_TYPE: {
        "title": "Неизвестный тип документа",
        "description": "Документы, у которых OCR-текст есть, но тип документа не распознан.",
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
        dict
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
        errors, warnings = validate_invoice_for_payment_registry(
            invoice
        )

        if category == BOT_REPORT_CATEGORY_READY and errors:
            continue

        if category == BOT_REPORT_CATEGORY_NOT_READY and not errors:
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
    return (
        Invoice.objects
        .select_related(
            "counterparty",
            "user",
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
