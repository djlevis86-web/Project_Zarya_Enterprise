from django.core.management.base import BaseCommand

from invoices.models import Invoice
from invoices.ocr_verification_service import (
    apply_ocr_amount_to_invoice,
)

from ocr.services import (
    extract_text_from_pdf,
    extract_text_from_image,
    parse_invoice_data
)


class Command(BaseCommand):

    help = 'Повторная OCR обработка всех счетов'

    def handle(self, *args, **kwargs):

        invoices = Invoice.objects.all()

        total = invoices.count()

        self.stdout.write(
            f'Найдено счетов: {total}'
        )

        processed = 0

        for invoice in invoices:

            try:

                file_path = invoice.file.path

                self.stdout.write(
                    f'Обработка #{invoice.id}'
                )

                if file_path.lower().endswith('.pdf'):

                    text = extract_text_from_pdf(
                        file_path
                    )

                else:

                    text = extract_text_from_image(
                        file_path
                    )

                invoice.ocr_text = text

                parsed = parse_invoice_data(
                    text
                )

                invoice.invoice_number = parsed.get(
                    'invoice_number'
                )

                invoice.invoice_date = parsed.get(
                    'invoice_date'
                )

                invoice.vendor = parsed.get(
                    'vendor'
                )

                amount_warning = apply_ocr_amount_to_invoice(
                    invoice,
                    parsed.get(
                        'amount'
                    )
                )

                if amount_warning:
                    invoice.ocr_comment = (
                        f"{invoice.ocr_comment or ''} "
                        f"{amount_warning}"
                    ).strip()

                invoice.save()

                processed += 1

            except Exception as e:

                self.stdout.write(
                    self.style.ERROR(
                        f'Ошибка #{invoice.id}: {e}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Обработано: {processed}'
            )
        )