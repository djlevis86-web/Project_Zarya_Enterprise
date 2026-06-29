from decimal import Decimal
import traceback

from .log_service import create_invoice_log
from .models import Invoice

from ocr.services import (
    extract_text_from_image,
    extract_text_from_pdf,
    parse_invoice_data,
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

        amount = parsed.get(
            'amount'
        )

        amount_warning = ''

        if amount:

            try:

                ocr_amount = Decimal(
                    str(amount).replace(
                        ',',
                        '.'
                    )
                )

                invoice.ocr_amount = ocr_amount

                current_amount = invoice.amount or Decimal(
                    '0.00'
                )

                if current_amount == Decimal(
                    '0.00'
                ):

                    invoice.amount = ocr_amount
                    invoice.amount_verified = True
                    invoice.ocr_verified = True

                else:

                    invoice.amount_verified = (
                        Decimal(str(current_amount))
                        ==
                        ocr_amount
                    )

                    invoice.ocr_verified = invoice.amount_verified

            except Exception:

                invoice.ocr_amount = None
                invoice.amount_verified = False
                invoice.ocr_verified = False

                amount_warning = (
                    'OCR нашел сумму, но не удалось преобразовать ее в число.'
                )

        else:

            invoice.ocr_amount = None
            invoice.amount_verified = False
            invoice.ocr_verified = False

            amount_warning = 'OCR сумма не определена.'

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

