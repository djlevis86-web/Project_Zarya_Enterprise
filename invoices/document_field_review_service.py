from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Invoice, InvoiceFieldReview


MONEY_QUANT = Decimal("0.01")
SUPPORTED_FIELD_NAMES = frozenset(
    value for value, _label in InvoiceFieldReview.FIELD_CHOICES
)


class DocumentFieldReviewError(ValueError):
    pass


def _require_supported_field(field_name: str) -> str:
    normalized = str(field_name or "").strip()
    if normalized not in SUPPORTED_FIELD_NAMES:
        raise DocumentFieldReviewError(
            "Поле документа не поддерживает подтверждение."
        )
    return normalized


def _normalize_money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value).replace(",", ".")).quantize(
            MONEY_QUANT
        )
    except (InvalidOperation, TypeError, ValueError) as error:
        raise DocumentFieldReviewError(
            "Введите корректную сумму."
        ) from error

    if amount <= Decimal("0.00"):
        raise DocumentFieldReviewError(
            "Сумма должна быть больше нуля."
        )
    return amount


def _normalize_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value or "").strip()
    parsed = parse_date(raw)
    if parsed is None:
        try:
            parsed = datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError as error:
            raise DocumentFieldReviewError(
                "Введите корректную дату документа."
            ) from error
    return parsed


def _normalize_text(value: object, *, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise DocumentFieldReviewError(
            f"Поле «{label}» не может быть пустым."
        )
    return normalized


def serialize_field_value(
    invoice: Invoice,
    field_name: str,
    *,
    recognized: bool = False,
) -> str:
    field_name = _require_supported_field(field_name)

    if field_name == InvoiceFieldReview.FIELD_AMOUNT:
        value = invoice.ocr_amount if recognized else invoice.amount
        if value is None:
            return ""
        try:
            return format(Decimal(str(value)).quantize(MONEY_QUANT), ".2f")
        except (InvalidOperation, TypeError, ValueError):
            return str(value).strip()

    if field_name == InvoiceFieldReview.FIELD_INVOICE_NUMBER:
        return str(invoice.invoice_number or "").strip()

    if field_name == InvoiceFieldReview.FIELD_DOCUMENT_DATE:
        value = invoice.document_date or invoice.invoice_date
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")
        return str(value or "").strip()

    return str(invoice.vendor or "").strip()


def serialize_recognized_value(
    field_name: str,
    value: object,
) -> str:
    field_name = _require_supported_field(field_name)
    if value is None:
        return ""

    if field_name == InvoiceFieldReview.FIELD_AMOUNT:
        try:
            return format(
                Decimal(str(value).replace(",", ".")).quantize(MONEY_QUANT),
                ".2f",
            )
        except (InvalidOperation, TypeError, ValueError):
            return str(value).strip()

    if field_name == InvoiceFieldReview.FIELD_DOCUMENT_DATE:
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.isoformat()

    return str(value).strip()


def _legacy_confirmation_defaults(
    invoice: Invoice,
    field_name: str,
) -> dict[str, object]:
    current_value = serialize_field_value(invoice, field_name)
    recognized_value = (
        serialize_field_value(invoice, field_name, recognized=True)
        if field_name == InvoiceFieldReview.FIELD_AMOUNT
        else current_value
    )
    is_confirmed = bool(
        field_name == InvoiceFieldReview.FIELD_AMOUNT
        and invoice.amount_verified
        and current_value
    )
    return {
        "recognized_value": recognized_value,
        "current_value": current_value,
        "confirmed_value": current_value if is_confirmed else "",
        "is_confirmed": is_confirmed,
        "confirmed_at": invoice.updated_at if is_confirmed else None,
    }


def ensure_field_review(
    invoice: Invoice,
    field_name: str,
) -> InvoiceFieldReview:
    field_name = _require_supported_field(field_name)
    if not invoice.pk:
        raise DocumentFieldReviewError(
            "Сначала сохраните документ."
        )

    review, _created = InvoiceFieldReview.objects.get_or_create(
        invoice=invoice,
        field_name=field_name,
        defaults=_legacy_confirmation_defaults(invoice, field_name),
    )
    return review


def is_field_confirmed(
    invoice: Invoice,
    field_name: str,
) -> bool:
    field_name = _require_supported_field(field_name)
    annotation_name = f"field_review_{field_name}_confirmed"
    if hasattr(invoice, annotation_name):
        return bool(getattr(invoice, annotation_name))

    if (
        field_name == InvoiceFieldReview.FIELD_AMOUNT
        and invoice.amount_verified
    ):
        return True

    if not invoice.pk:
        return False

    return InvoiceFieldReview.objects.filter(
        invoice_id=invoice.pk,
        field_name=field_name,
        is_confirmed=True,
    ).exists()


def sync_ocr_field_review(
    invoice: Invoice,
    field_name: str,
    recognized_value: object,
) -> InvoiceFieldReview | None:
    field_name = _require_supported_field(field_name)
    if not invoice.pk:
        return None

    review = ensure_field_review(invoice, field_name)
    review.recognized_value = serialize_recognized_value(
        field_name,
        recognized_value,
    )
    review.current_value = serialize_field_value(invoice, field_name)

    if (
        field_name == InvoiceFieldReview.FIELD_AMOUNT
        and invoice.amount_verified
        and review.current_value
    ):
        review.is_confirmed = True
        review.confirmed_value = review.current_value
        if review.confirmed_at is None:
            review.confirmed_at = timezone.now()

    review.save(
        update_fields=(
            "recognized_value",
            "current_value",
            "confirmed_value",
            "is_confirmed",
            "confirmed_at",
            "updated_at",
        )
    )
    return review


def sync_manual_field_review(
    invoice: Invoice,
    field_name: str,
) -> InvoiceFieldReview | None:
    field_name = _require_supported_field(field_name)
    if not invoice.pk:
        return None

    review = ensure_field_review(invoice, field_name)
    current_value = serialize_field_value(invoice, field_name)
    review.current_value = current_value

    if review.is_confirmed and review.confirmed_value != current_value:
        review.is_confirmed = False
        review.confirmed_value = ""
        review.confirmed_by = None
        review.confirmed_at = None

    review.save(
        update_fields=(
            "current_value",
            "confirmed_value",
            "is_confirmed",
            "confirmed_by",
            "confirmed_at",
            "updated_at",
        )
    )
    return review


def apply_unconfirmed_system_value(
    invoice: Invoice,
    field_name: str,
    value: object,
) -> bool:
    field_name = _require_supported_field(field_name)
    if is_field_confirmed(invoice, field_name):
        return False

    if field_name == InvoiceFieldReview.FIELD_VENDOR:
        invoice.vendor = str(value or "").strip() or None
    elif field_name == InvoiceFieldReview.FIELD_INVOICE_NUMBER:
        invoice.invoice_number = str(value or "").strip() or None
    else:
        raise DocumentFieldReviewError(
            "Системное обновление этого поля не поддерживается."
        )
    return True


def _normalized_confirmation(
    field_name: str,
    value: object,
) -> tuple[object, str]:
    if field_name == InvoiceFieldReview.FIELD_AMOUNT:
        normalized = _normalize_money(value)
        return normalized, format(normalized, ".2f")

    if field_name == InvoiceFieldReview.FIELD_DOCUMENT_DATE:
        normalized = _normalize_date(value)
        return normalized, normalized.isoformat()

    if field_name == InvoiceFieldReview.FIELD_INVOICE_NUMBER:
        normalized = _normalize_text(value, label="Номер документа")
        return normalized, normalized

    normalized = _normalize_text(value, label="Поставщик")
    return normalized, normalized


def _set_invoice_confirmed_value(
    invoice: Invoice,
    field_name: str,
    normalized_value: object,
) -> list[str]:
    if field_name == InvoiceFieldReview.FIELD_AMOUNT:
        invoice.amount = normalized_value
        return ["amount"]

    if field_name == InvoiceFieldReview.FIELD_INVOICE_NUMBER:
        invoice.invoice_number = normalized_value
        return ["invoice_number"]

    if field_name == InvoiceFieldReview.FIELD_DOCUMENT_DATE:
        invoice.document_date = normalized_value
        return ["document_date"]

    invoice.vendor = normalized_value
    return ["vendor"]


@transaction.atomic
def confirm_invoice_field(
    invoice: Invoice,
    field_name: str,
    user,
    *,
    value: object | None = None,
) -> InvoiceFieldReview:
    field_name = _require_supported_field(field_name)
    locked_invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    review = ensure_field_review(locked_invoice, field_name)
    review = InvoiceFieldReview.objects.select_for_update().get(pk=review.pk)

    raw_value = (
        serialize_field_value(locked_invoice, field_name)
        if value is None or str(value).strip() == ""
        else value
    )
    normalized_value, serialized_value = _normalized_confirmation(
        field_name,
        raw_value,
    )
    update_fields = _set_invoice_confirmed_value(
        locked_invoice,
        field_name,
        normalized_value,
    )

    if field_name == InvoiceFieldReview.FIELD_AMOUNT:
        from .ocr_verification_service import sync_invoice_amount_verification

        sync_invoice_amount_verification(
            locked_invoice,
            source_label="подтверждения поля документа",
            save=False,
        )
        update_fields.extend(
            [
                "amount_verified",
                "ocr_verified",
                "ocr_comment",
            ]
        )

    if any(
        field.name == "updated_at"
        for field in locked_invoice._meta.fields
    ):
        update_fields.append("updated_at")

    locked_invoice.save(update_fields=tuple(dict.fromkeys(update_fields)))

    review.current_value = serialized_value
    review.confirmed_value = serialized_value
    review.is_confirmed = True
    review.confirmed_by = user
    review.confirmed_at = timezone.now()
    review.save(
        update_fields=(
            "current_value",
            "confirmed_value",
            "is_confirmed",
            "confirmed_by",
            "confirmed_at",
            "updated_at",
        )
    )

    for field in (
        "amount",
        "amount_verified",
        "ocr_verified",
        "ocr_comment",
        "invoice_number",
        "document_date",
        "vendor",
        "updated_at",
    ):
        setattr(invoice, field, getattr(locked_invoice, field))

    return review
