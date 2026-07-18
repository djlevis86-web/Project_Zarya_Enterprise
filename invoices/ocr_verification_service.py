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
    Подтверждает итоговую сумму после её ручного изменения.

    Правило:
    - положительная сумма, изменённая пользователем, считается подтверждённой;
    - OCR используется только для дополнительного сравнения;
    - несовпадение с OCR не отменяет ручное подтверждение;
    - ocr_verified показывает только факт совпадения с OCR.
    """

    old_amount_verified = invoice.amount_verified
    old_ocr_verified = invoice.ocr_verified
    old_ocr_comment = invoice.ocr_comment or ""

    amount = normalize_money(
        invoice.amount
    )
    ocr_amount = normalize_money(
        invoice.ocr_amount
    )

    if (
        amount is None
        or amount <= Decimal("0.00")
    ):
        invoice.amount_verified = False
        invoice.ocr_verified = False

        message = (
            f"Сумма не подтверждена после {source_label}: "
            "укажите положительную сумму."
        )

    else:
        invoice.amount_verified = True

        if ocr_amount is None:
            invoice.ocr_verified = False

            message = (
                f"Сумма подтверждена вручную после {source_label}. "
                "OCR-сумма не определена."
            )

        elif amount == ocr_amount:
            invoice.ocr_verified = True

            message = (
                f"Сумма подтверждена вручную после {source_label} "
                "и совпадает с OCR-суммой."
            )

        else:
            invoice.ocr_verified = False

            message = (
                f"Сумма подтверждена вручную после {source_label}: "
                f"подтверждённая сумма {amount} отличается "
                f"от OCR-суммы {ocr_amount}. "
                "Приоритет имеет сумма, проверенная пользователем."
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


def apply_ocr_amount_to_invoice(
    invoice,
    raw_amount,
    prefill_amount_from_ocr=False,
):
    """
    Применяет результат OCR, не отменяя ручное подтверждение.

    Правило:
    - новый документ может получить OCR-сумму как предварительную;
    - предварительная OCR-сумма не подтверждается автоматически;
    - ранее подтверждённая пользователем сумма сохраняет приоритет;
    - повторный OCR обновляет ocr_amount и ocr_verified,
      но не снимает amount_verified.
    """

    current_amount = (
        normalize_money(
            invoice.amount
        )
        or Decimal("0.00")
    )

    manual_amount_was_verified = bool(
        invoice.amount_verified
        and current_amount > Decimal("0.00")
    )

    if raw_amount:
        try:
            ocr_amount = normalize_money(
                str(raw_amount).replace(
                    ",",
                    "."
                )
            )

            if ocr_amount is None:
                raise ValueError(
                    "OCR amount cannot be converted to Decimal"
                )

            invoice.ocr_amount = ocr_amount

            if (
                prefill_amount_from_ocr
                or current_amount == Decimal("0.00")
            ):
                invoice.amount = ocr_amount
                invoice.amount_verified = False
                invoice.ocr_verified = False

                return (
                    "OCR-сумма автоматически подставлена. "
                    "Требуется ручное подтверждение."
                )

            if manual_amount_was_verified:
                invoice.amount_verified = True
                invoice.ocr_verified = (
                    current_amount == ocr_amount
                )

                if invoice.ocr_verified:
                    return (
                        "OCR-сумма совпадает с подтверждённой "
                        "пользователем суммой. "
                        "Ручное подтверждение сохранено."
                    )

                return (
                    f"OCR-сумма {ocr_amount} отличается от "
                    f"подтверждённой пользователем суммы "
                    f"{current_amount}. "
                    "Ручное подтверждение сохранено и имеет приоритет."
                )

            invoice.amount_verified = False
            invoice.ocr_verified = False

            if current_amount == ocr_amount:
                return (
                    "OCR-сумма совпадает с суммой в системе. "
                    "Требуется ручное подтверждение."
                )

            return ""

        except Exception:
            invoice.ocr_amount = None
            invoice.amount_verified = (
                manual_amount_was_verified
            )
            invoice.ocr_verified = False

            if manual_amount_was_verified:
                return (
                    "OCR нашёл сумму, но не удалось преобразовать "
                    "её в число. Ручное подтверждение сохранено."
                )

            return (
                "OCR нашёл сумму, но не удалось преобразовать "
                "её в число."
            )

    invoice.ocr_amount = None
    invoice.amount_verified = (
        manual_amount_was_verified
    )
    invoice.ocr_verified = False

    if manual_amount_was_verified:
        return (
            "OCR-сумма не определена. "
            "Ручное подтверждение суммы сохранено."
        )

    return "OCR-сумма не определена."

