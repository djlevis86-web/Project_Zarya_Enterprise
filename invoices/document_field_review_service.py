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
    if not recognized_value:
        recognized_source = InvoiceFieldReview.SOURCE_UNKNOWN
    elif field_name == InvoiceFieldReview.FIELD_AMOUNT:
        recognized_source = InvoiceFieldReview.SOURCE_LEGACY_OCR
    else:
        recognized_source = InvoiceFieldReview.SOURCE_LEGACY_CURRENT
    is_confirmed = bool(
        field_name == InvoiceFieldReview.FIELD_AMOUNT
        and invoice.amount_verified
        and current_value
    )
    return {
        "recognized_value": recognized_value,
        "recognized_source": recognized_source,
        "recognized_at": None,
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


def _display_review_value(field_name: str, value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Не указано"

    if field_name == InvoiceFieldReview.FIELD_AMOUNT:
        try:
            amount = Decimal(raw.replace(",", ".")).quantize(MONEY_QUANT)
        except (InvalidOperation, TypeError, ValueError):
            return raw
        formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        return formatted + " ₽"

    if field_name == InvoiceFieldReview.FIELD_DOCUMENT_DATE:
        parsed = parse_date(raw)
        if parsed is not None:
            return parsed.strftime("%d.%m.%Y")

    return raw


def _confirmed_by_label(user) -> str:
    if user is None:
        return ""
    full_name = ""
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = str(get_full_name() or "").strip()
    return full_name or str(getattr(user, "username", "") or "").strip()


def _normalized_comparison_text(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _recognized_source_contract(review) -> dict[str, object]:
    source = (
        str(getattr(review, "recognized_source", "") or "").strip()
        if review is not None
        else InvoiceFieldReview.SOURCE_UNKNOWN
    )
    labels = {
        InvoiceFieldReview.SOURCE_OCR: "Распознавание документа",
        InvoiceFieldReview.SOURCE_LEGACY_OCR: (
            "Распознавание до фиксации источника"
        ),
        InvoiceFieldReview.SOURCE_LEGACY_CURRENT: (
            "Перенесено из текущих данных"
        ),
        InvoiceFieldReview.SOURCE_UNKNOWN: "Источник не подтверждён",
    }
    details = {
        InvoiceFieldReview.SOURCE_OCR: (
            "Значение сохранено во время фактического распознавания документа."
        ),
        InvoiceFieldReview.SOURCE_LEGACY_OCR: (
            "Значение было получено распознаванием до появления точной фиксации источника."
        ),
        InvoiceFieldReview.SOURCE_LEGACY_CURRENT: (
            "Значение перенесено из прежних полей системы и не считается доказанным результатом распознавания."
        ),
        InvoiceFieldReview.SOURCE_UNKNOWN: (
            "Для значения нет доказанного источника из документа."
        ),
    }
    is_document_evidence = source in {
        InvoiceFieldReview.SOURCE_OCR,
        InvoiceFieldReview.SOURCE_LEGACY_OCR,
    }
    return {
        "recognized_source": source,
        "recognized_source_label": labels.get(
            source, labels[InvoiceFieldReview.SOURCE_UNKNOWN]
        ),
        "recognized_source_detail": details.get(
            source, details[InvoiceFieldReview.SOURCE_UNKNOWN]
        ),
        "recognized_is_document_evidence": is_document_evidence,
    }


def _reference_contract(invoice: Invoice, field_name: str) -> dict[str, object]:
    empty = {
        "reference_available": False,
        "reference_value": "",
        "reference_display": "Не применяется",
        "reference_source_label": "Справочник не применяется",
        "reference_detail": "",
    }
    if field_name != InvoiceFieldReview.FIELD_VENDOR:
        return empty

    counterparty = getattr(invoice, "counterparty", None)
    if counterparty is None:
        return {
            **empty,
            "reference_display": "Не сопоставлен",
            "reference_source_label": "Справочник контрагентов",
            "reference_detail": (
                "Документ ещё не сопоставлен с записью справочника."
            ),
        }

    value = str(
        getattr(counterparty, "full_name", "")
        or getattr(counterparty, "name", "")
        or ""
    ).strip()
    source = str(getattr(counterparty, "source", "") or "").strip()
    source_labels = {
        "1c": "Справочник 1С",
        "manual": "Ручной справочник",
        "ocr": "Справочник из распознавания",
    }
    requisites = []
    inn = str(getattr(counterparty, "inn", "") or "").strip()
    kpp = str(getattr(counterparty, "kpp", "") or "").strip()
    if inn:
        requisites.append("ИНН " + inn)
    if kpp:
        requisites.append("КПП " + kpp)

    return {
        "reference_available": bool(value),
        "reference_value": value,
        "reference_display": _display_review_value(field_name, value),
        "reference_source_label": source_labels.get(
            source, "Справочник контрагентов"
        ),
        "reference_detail": " · ".join(requisites),
    }


def build_invoice_field_review_workspace(
    invoice: Invoice,
    reviews=None,
) -> dict[str, object]:
    """Build the read-only V19 interaction presentation for review fields.

    This helper never writes on GET. Missing rows are represented from the
    current invoice values so manually-created legacy fixtures remain readable.
    """
    review_items = list(
        reviews
        if reviews is not None
        else invoice.field_reviews.select_related("confirmed_by")
    )
    reviews_by_field = {item.field_name: item for item in review_items}

    input_contracts = {
        InvoiceFieldReview.FIELD_AMOUNT: {
            "input_type": "number",
            "input_mode": "decimal",
            "input_step": "0.01",
            "placeholder": "0,00",
        },
        InvoiceFieldReview.FIELD_INVOICE_NUMBER: {
            "input_type": "text",
            "input_mode": "text",
            "input_step": "",
            "placeholder": "Номер документа",
        },
        InvoiceFieldReview.FIELD_DOCUMENT_DATE: {
            "input_type": "date",
            "input_mode": "numeric",
            "input_step": "",
            "placeholder": "",
        },
        InvoiceFieldReview.FIELD_VENDOR: {
            "input_type": "text",
            "input_mode": "text",
            "input_step": "",
            "placeholder": "Наименование поставщика",
        },
    }

    rows = []
    confirmed_count = 0
    attention_count = 0

    for field_name, label in InvoiceFieldReview.FIELD_CHOICES:
        review = reviews_by_field.get(field_name)
        current_value = serialize_field_value(invoice, field_name)
        if review is not None:
            raw_recognized_value = str(review.recognized_value or "").strip()
            confirmed_value = str(review.confirmed_value or "").strip()
            is_confirmed = bool(review.is_confirmed)
            recognized_at = review.recognized_at
            confirmed_by = review.confirmed_by
            confirmed_at = review.confirmed_at
        else:
            raw_recognized_value = (
                serialize_field_value(invoice, field_name, recognized=True)
                if field_name == InvoiceFieldReview.FIELD_AMOUNT
                else current_value
            )
            confirmed_value = (
                current_value
                if field_name == InvoiceFieldReview.FIELD_AMOUNT
                and invoice.amount_verified
                and current_value
                else ""
            )
            is_confirmed = bool(confirmed_value)
            recognized_at = None
            confirmed_by = None
            confirmed_at = None

        source_contract = _recognized_source_contract(review)
        recognized_value = (
            raw_recognized_value
            if source_contract["recognized_is_document_evidence"]
            else ""
        )
        reference_contract = _reference_contract(invoice, field_name)

        if is_confirmed:
            status_code = "confirmed"
            status_label = "Подтверждено"
            status_tone = "success"
            status_detail = "Итоговое значение защищено от повторного распознавания."
            confirmed_count += 1
        elif not current_value:
            status_code = "missing"
            status_label = "Не заполнено"
            status_tone = "danger"
            status_detail = "Заполните итоговое значение и подтвердите его."
            attention_count += 1
        elif not recognized_value:
            status_code = "unrecognized"
            status_tone = "warning"
            if (
                raw_recognized_value
                and source_contract["recognized_source"]
                == InvoiceFieldReview.SOURCE_LEGACY_CURRENT
            ):
                status_label = "Источник не подтверждён"
                status_detail = (
                    "Прежнее значение перенесено из системы и не считается "
                    "доказанным результатом распознавания."
                )
            else:
                status_label = "Нет данных из документа"
                status_detail = (
                    "Сверьте значение с оригиналом перед подтверждением."
                )
            attention_count += 1
        elif current_value == recognized_value:
            status_code = "matched"
            status_label = "Совпадает"
            status_tone = "info"
            status_detail = "Значения совпадают, но итог ещё не подтверждён пользователем."
            attention_count += 1
        else:
            status_code = "mismatch"
            status_label = "Есть расхождение"
            status_tone = "warning"
            status_detail = "Выберите итоговое значение после сверки с оригиналом."
            attention_count += 1

        recognized_at_label = ""
        if recognized_at is not None:
            recognized_display_time = (
                timezone.localtime(recognized_at)
                if timezone.is_aware(recognized_at)
                else recognized_at
            )
            recognized_at_label = recognized_display_time.strftime(
                "%d.%m.%Y %H:%M"
            )

        confirmed_at_label = ""
        if confirmed_at is not None:
            display_time = (
                timezone.localtime(confirmed_at)
                if timezone.is_aware(confirmed_at)
                else confirmed_at
            )
            confirmed_at_label = display_time.strftime("%d.%m.%Y %H:%M")

        rows.append(
            {
                "field_name": field_name,
                "label": label,
                "recognized_value": recognized_value,
                "recognized_display": (
                    _display_review_value(field_name, recognized_value)
                    if source_contract["recognized_is_document_evidence"]
                    else "Нет доказанного значения"
                ),
                "raw_recognized_value": raw_recognized_value,
                "raw_recognized_display": _display_review_value(
                    field_name, raw_recognized_value
                ),
                "current_value": current_value,
                "current_display": _display_review_value(
                    field_name, current_value
                ),
                "confirmed_value": confirmed_value,
                "confirmed_display": _display_review_value(
                    field_name, confirmed_value
                ),
                "confirmation_value": current_value or recognized_value,
                "is_confirmed": is_confirmed,
                "status_code": status_code,
                "status_label": status_label,
                "status_tone": status_tone,
                "status_detail": status_detail,
                "recognized_matches_current": bool(
                    current_value
                    and recognized_value
                    and current_value == recognized_value
                ),
                "reference_matches_current": bool(
                    current_value
                    and reference_contract["reference_value"]
                    and _normalized_comparison_text(current_value)
                    == _normalized_comparison_text(
                        reference_contract["reference_value"]
                    )
                ),
                "recognized_at_label": recognized_at_label,
                "confirmed_by_label": _confirmed_by_label(confirmed_by),
                "confirmed_at_label": confirmed_at_label,
                **source_contract,
                **reference_contract,
                **input_contracts[field_name],
            }
        )

    return {
        "rows": rows,
        "total_count": len(rows),
        "confirmed_count": confirmed_count,
        "attention_count": attention_count,
        "is_complete": confirmed_count == len(rows),
    }


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
    review.recognized_source = InvoiceFieldReview.SOURCE_OCR
    review.recognized_at = timezone.now()
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
            "recognized_source",
            "recognized_at",
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
