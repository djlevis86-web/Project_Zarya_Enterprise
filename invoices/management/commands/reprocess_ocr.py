from django.core.management.base import BaseCommand

from invoices.models import Invoice
from invoices.models import Counterparty

from invoices.counterparty_service import (
    get_or_create_counterparty_from_invoice
)

from ocr.services import (
    extract_text_from_pdf,
    extract_text_from_image,
    parse_invoice_data
)


class Command(BaseCommand):

    help = 'Повторно распознает OCR для уже загруженных счетов'

    def add_arguments(self, parser):

        parser.add_argument(
            '--all',
            action='store_true',
            help='Обработать все счета'
        )

        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Обработать только счета без OCR-текста'
        )

        parser.add_argument(
            '--reset-counterparties',
            action='store_true',
            help='Удалить автосозданных контрагентов и привязать заново'
        )

        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Ограничить количество счетов'
        )

    def handle(self, *args, **options):

        if options['reset_counterparties']:

            self.stdout.write(
                'Сбрасываю связи с контрагентами...'
            )

            Invoice.objects.update(
                counterparty=None,
                counterparty_match_status=Invoice.COUNTERPARTY_MATCH_NOT_PROCESSED,
                counterparty_match_comment=''
            )

            deleted_count, _ = Counterparty.objects.filter(
                source=Counterparty.SOURCE_OCR
            ).delete()

            self.stdout.write(
                self.style.WARNING(
                    f'OCR-контрагенты удалены: {deleted_count}. Контрагенты из 1С сохранены.'
                )
            )

        invoices = Invoice.objects.exclude(
            file=''
        ).order_by(
            'id'
        )

        if options['only_missing']:

            invoices = invoices.filter(
                ocr_text__isnull=True
            )

        if options['limit']:

            invoices = invoices[:options['limit']]

        total = invoices.count()

        self.stdout.write(
            f'Найдено счетов для OCR: {total}'
        )

        processed = 0
        skipped = 0
        errors = 0

        for invoice in invoices:

            try:

                if not invoice.file:

                    skipped += 1

                    self.stdout.write(
                        f'#{invoice.id} пропущен: нет файла'
                    )

                    continue

                file_path = invoice.file.path

                self.stdout.write(
                    f'#{invoice.id} OCR: {file_path}'
                )

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

                invoice.invoice_number = parsed.get(
                    'invoice_number'
                )

                invoice.invoice_date = parsed.get(
                    'invoice_date'
                )

                invoice.vendor = parsed.get(
                    'vendor'
                )

                amount = parsed.get(
                    'amount'
                )

                if amount:

                    try:

                        invoice.ocr_amount = float(
                            str(amount).replace(
                                ',',
                                '.'
                            )
                        )

                        if (
                            invoice.amount is None
                            or
                            float(invoice.amount) == 0
                        ):

                            invoice.amount = invoice.ocr_amount

                            invoice.amount_verified = False
                            invoice.ocr_verified = False

                        else:

                            invoice.amount_verified = False
                            invoice.ocr_verified = False

                    except Exception:

                        invoice.amount_verified = False
                        invoice.ocr_verified = False

                invoice.counterparty = (
                    get_or_create_counterparty_from_invoice(
                        invoice
                    )
                )

                invoice.save()

                processed += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'#{invoice.id} OK | '
                        f'vendor={invoice.vendor} | '
                        f'counterparty={invoice.counterparty} | '
                        f'number={invoice.invoice_number} | '
                        f'amount={invoice.ocr_amount}'
                    )
                )

            except Exception as error:

                errors += 1

                self.stdout.write(
                    self.style.ERROR(
                        f'#{invoice.id} ERROR: {error}'
                    )
                )

        self.stdout.write(
            '---'
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово. Обработано: {processed}, '
                f'пропущено: {skipped}, '
                f'ошибок: {errors}'
            )
        )

        self.stdout.write(
            f'Контрагентов в базе: {Counterparty.objects.count()}'
        )