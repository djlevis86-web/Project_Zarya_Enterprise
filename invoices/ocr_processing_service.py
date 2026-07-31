import traceback

from .document_field_review_service import (
    apply_unconfirmed_system_value,
    is_field_confirmed,
    sync_ocr_field_review,
    sync_manual_field_review,
)
from .log_service import create_invoice_log
from .models import Invoice, InvoiceFieldReview
from .ocr_verification_service import apply_ocr_amount_to_invoice

from ocr.services import (
    extract_text_from_image,
    extract_text_from_pdf,
    extract_text_from_pdf_light,
    is_ocr_timeout_error,
    parse_invoice_data,
)


def extract_invoice_text_with_light_fallback(file_path):
    file_path = str(file_path)

    if not file_path.lower().endswith(
        ".pdf"
    ):
        return (
            extract_text_from_image(
                file_path
            ),
            False,
        )

    try:
        return (
            extract_text_from_pdf(
                file_path
            ),
            False,
        )

    except Exception as error:
        if not is_ocr_timeout_error(
            error
        ):
            raise

        light_text = extract_text_from_pdf_light(
            file_path
        )

        if not light_text:
            raise

        return (
            light_text,
            True,
        )


def read_and_parse_invoice_file(file_path):
    text, _used_light_ocr = extract_invoice_text_with_light_fallback(
        file_path
    )

    parsed = parse_invoice_data(
        text
    )

    return text, parsed




def get_duplicate_invoice_by_ocr_identity(invoice, parsed):
    parsed_invoice_number = parsed.get(
        'invoice_number'
    )

    parsed_invoice_date = parsed.get(
        'invoice_date'
    )

    if not parsed_invoice_number or not parsed_invoice_date:
        return None

    return (
        Invoice.objects
        .filter(
            invoice_number=parsed_invoice_number,
            invoice_date=parsed_invoice_date,
        )
        .exclude(
            id=invoice.id
        )
        .exclude(
            status=Invoice.STATUS_REJECTED
        )
        .first()
    )


def apply_ocr_identity_to_invoice(invoice, parsed):
    """
    Применяет OCR-идентичность, не перезаписывая подтверждённые поля.

    Распознанные значения сохраняются в InvoiceFieldReview после
    сохранения документа. Подтверждённые пользователем номер, дата и
    поставщик остаются источником истины при повторном OCR.
    """

    parsed_invoice_number = parsed.get("invoice_number")
    parsed_invoice_date = parsed.get("invoice_date")
    number_warning = ""
    number_is_confirmed = is_field_confirmed(
        invoice,
        InvoiceFieldReview.FIELD_INVOICE_NUMBER,
    )

    if not number_is_confirmed:
        if parsed_invoice_number and parsed_invoice_date:
            duplicate_invoice = get_duplicate_invoice_by_ocr_identity(
                invoice,
                parsed,
            )
            if duplicate_invoice:
                number_warning = (
                    f"OCR нашел номер {parsed_invoice_number} "
                    f"от {parsed_invoice_date}, "
                    f"но такой счет уже есть: #{duplicate_invoice.id}. "
                    "Номер текущего счета не изменен."
                )
            else:
                invoice.invoice_number = parsed_invoice_number
        elif parsed_invoice_number:
            invoice.invoice_number = parsed_invoice_number
        else:
            invoice.invoice_number = None

    date_is_confirmed = is_field_confirmed(
        invoice,
        InvoiceFieldReview.FIELD_DOCUMENT_DATE,
    )
    if not date_is_confirmed:
        invoice.invoice_date = parsed_invoice_date
        parsed_document_date = parsed.get("document_date")
        if parsed_document_date:
            invoice.document_date = parsed_document_date

    apply_unconfirmed_system_value(
        invoice,
        InvoiceFieldReview.FIELD_VENDOR,
        parsed.get("vendor"),
    )

    parsed_document_type = parsed.get("document_type")
    if parsed_document_type in (
        Invoice.DOCUMENT_TYPE_INVOICE,
        Invoice.DOCUMENT_TYPE_UPD,
        Invoice.DOCUMENT_TYPE_WAYBILL,
        Invoice.DOCUMENT_TYPE_PAYMENT_DOCUMENT,
        Invoice.DOCUMENT_TYPE_UNKNOWN,
    ):
        invoice.document_type = parsed_document_type

    return number_warning


def sync_identity_reviews_after_ocr(invoice, parsed):
    sync_ocr_field_review(
        invoice,
        InvoiceFieldReview.FIELD_INVOICE_NUMBER,
        parsed.get("invoice_number"),
    )
    sync_ocr_field_review(
        invoice,
        InvoiceFieldReview.FIELD_DOCUMENT_DATE,
        parsed.get("document_date") or parsed.get("invoice_date"),
    )
    sync_ocr_field_review(
        invoice,
        InvoiceFieldReview.FIELD_VENDOR,
        parsed.get("vendor"),
    )
    sync_ocr_field_review(
        invoice,
        InvoiceFieldReview.FIELD_AMOUNT,
        parsed.get("amount"),
    )


def run_invoice_ocr_processing(invoice, user, log_action):

    if not invoice.file:

        create_invoice_log(
            invoice,
            user,
            'OCR не выполнен: у счета нет файла'
        )

        return False, 'у счета нет файла'

    try:

        file_path = invoice.file.path

        text, used_light_ocr = extract_invoice_text_with_light_fallback(
            file_path
        )

        parsed = parse_invoice_data(
            text
        )

        invoice.ocr_text = text

        number_warning = apply_ocr_identity_to_invoice(
            invoice,
            parsed
        )

        amount_warning = apply_ocr_amount_to_invoice(
            invoice,
            parsed.get(
                'amount'
            )
        )

        ocr_comments = [
            log_action
        ]

        if used_light_ocr:
            ocr_comments.append(
                "OCR выполнен облегчённым режимом после таймаута обычного OCR."
            )

        if number_warning:

            ocr_comments.append(
                number_warning
            )

        if amount_warning:

            ocr_comments.append(
                amount_warning
            )

        invoice.ocr_comment = ' '.join(
            ocr_comments
        )

        invoice.save()

        sync_identity_reviews_after_ocr(
            invoice,
            parsed,
        )

        try:

            from .counterparty_service import get_or_create_counterparty_from_invoice

            invoice.counterparty = None

            counterparty = get_or_create_counterparty_from_invoice(
                invoice
            )

            invoice.counterparty = counterparty

            update_fields = [
                'counterparty',
                'counterparty_match_status',
                'counterparty_match_comment',
            ]

            if counterparty and apply_unconfirmed_system_value(
                invoice,
                InvoiceFieldReview.FIELD_VENDOR,
                counterparty.name,
            ):
                update_fields.append(
                    'vendor'
                )

            invoice.save(
                update_fields=update_fields
            )

            if 'vendor' in update_fields:
                sync_manual_field_review(
                    invoice,
                    InvoiceFieldReview.FIELD_VENDOR,
                )

        except Exception as match_error:

            create_invoice_log(
                invoice,
                user,
                f'Ошибка сопоставления контрагента после OCR: {match_error}'
            )

        create_invoice_log(
            invoice,
            user,
            log_action
        )

        if number_warning:

            return True, number_warning

        if used_light_ocr:
            return True, 'OCR успешно обновлен облегчённым режимом'

        return True, 'OCR успешно обновлен'

    except Exception as error:

        traceback.print_exc()

        create_invoice_log(
            invoice,
            user,
            f'OCR ошибка: {error}'
        )

        return False, str(error)
