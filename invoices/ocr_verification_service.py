from decimal import Decimal, InvalidOperation


MONEY_QUANT = Decimal("0.01")


def normalize_money(value):
    if value is None:
        return None

    try:
        return Decimal(str(value)).quantize(MONEY_QUANT)
    except (InvalidOperation, TypeError, ValueError):
        return None


def sync_invoice_amount_verification(
    invoice,
    source_label="редактирования счёта",
    save=True,
):
    """
    Синхронизирует OCR-статус суммы после изменения подтвержденной суммы.

    Правило:
    - если OCR-суммы нет: сумма не подтверждена;
    - если amount == ocr_amount: сумма подтверждена;
    - если amount != ocr_amount: сумма требует проверки.
    """

    old_amount_verified = invoice.amount_verified
    old_ocr_verified = invoice.ocr_verified
    old_ocr_comment = invoice.ocr_comment or ""

    amount = normalize_money(invoice.amount)
    ocr_amount = normalize_money(invoice.ocr_amount)

    if ocr_amount is None:
        invoice.amount_verified = False
        invoice.ocr_verified = False
        message = (
            f"Сумма требует ручной проверки после {source_label}: "
            "OCR сумма не определена."
        )

    elif amount == ocr_amount:
        invoice.amount_verified = True
        invoice.ocr_verified = True
        message = (
            f"Сумма подтверждена после {source_label}: "
            "подтвержденная сумма совпадает с OCR-суммой."
        )

    else:
        invoice.amount_verified = False
        invoice.ocr_verified = False
        message = (
            f"Сумма требует проверки после {source_label}: "
            "подтвержденная сумма отличается от OCR-суммы."
        )

    invoice.ocr_comment = message

    changed = (
        old_amount_verified != invoice.amount_verified
        or old_ocr_verified != invoice.ocr_verified
        or old_ocr_comment != invoice.ocr_comment
    )

    if save and changed:
        invoice.save(
            update_fields=[
                "amount_verified",
                "ocr_verified",
                "ocr_comment",
                "updated_at",
            ]
        )

    return changed, message
