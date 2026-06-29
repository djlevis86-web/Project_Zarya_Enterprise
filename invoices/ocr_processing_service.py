import traceback

from .log_service import create_invoice_log
from .models import Invoice
from .ocr_verification_service import apply_ocr_amount_to_invoice

from ocr.services import (
    extract_text_from_image,
    extract_text_from_pdf,
    parse_invoice_data,
)


def read_and_parse_invoice_file(file_path):
    file_path = str(file_path)

    if file_path.lower().endswith(
        ".pdf"
    ):
        text = extract_text_from_pdf(
            file_path
        )
    else:
        text = extract_text_from_image(
            file_path
        )

    parsed = parse_invoice_data(
        text
    )

    return text, parsed



def apply_ocr_identity_to_invoice(invoice, parsed):
    """
    Применяет к счету номер, дату и поставщика из OCR.

    Если OCR нашел номер и дату, но такой активный счет уже есть,
    номер текущего счета не меняем и возвращаем предупреждение.
    """

    parsed_invoice_number = parsed.get(
        'invoice_number'
    )

    parsed_invoice_date = parsed.get(
        'invoice_date'
    )

    number_warning = ''

    if parsed_invoice_number and parsed_invoice_date:

        duplicate_invoice = (
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

        if duplicate_invoice:

            number_warning = (
                f'OCR нашел номер {parsed_invoice_number} '
                f'от {parsed_invoice_date}, '
                f'но такой счет уже есть: #{duplicate_invoice.id}. '
                'Номер текущего счета не изменен.'
            )

        else:

            invoice.invoice_number = parsed_invoice_number

    elif parsed_invoice_number:

        invoice.invoice_number = parsed_invoice_number

    else:

        invoice.invoice_number = None

    invoice.invoice_date = parsed_invoice_date

    invoice.vendor = parsed.get(
        'vendor'
    )

    return number_warning


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

        if file_path.lower().endswith(
            '.pdf'
        ):

            text = extract_text_from_pdf(
                file_path
            )

        else:

            text = extract_text_from_image(
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

        try:

            from .counterparty_service import get_or_create_counterparty_from_invoice

            invoice.counterparty = None

            counterparty = get_or_create_counterparty_from_invoice(
                invoice
            )

            invoice.counterparty = counterparty

            invoice.save(
                update_fields=[
                    'counterparty',
                    'counterparty_match_status',
                    'counterparty_match_comment',
                ]
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

        return True, 'OCR успешно обновлен'

    except Exception as error:

        traceback.print_exc()

        create_invoice_log(
            invoice,
            user,
            f'OCR ошибка: {error}'
        )

        return False, str(error)

