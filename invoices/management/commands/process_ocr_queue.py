from django.core.management.base import BaseCommand
from django.utils import timezone

from invoices.models import OCRJob
from invoices.ocr_processing_service import run_invoice_ocr_processing


class Command(BaseCommand):

    help = 'Process pending OCR jobs.'

    def add_arguments(self, parser):

        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of jobs to process.'
        )

    def handle(self, *args, **options):

        limit = options[
            'limit'
        ]

        jobs = list(
            OCRJob.objects
            .select_related(
                'invoice',
                'user',
                'invoice__user',
            )
            .filter(
                status=OCRJob.STATUS_PENDING
            )
            .order_by(
                'created_at'
            )[:limit]
        )

        if not jobs:

            self.stdout.write(
                self.style.WARNING(
                    'Нет задач OCR в очереди.'
                )
            )

            return

        success_count = 0
        error_count = 0

        for job in jobs:

            job.status = OCRJob.STATUS_PROCESSING
            job.started_at = timezone.now()
            job.attempts += 1
            job.error_message = ''
            job.message = 'OCR выполняется.'

            job.save(
                update_fields=[
                    'status',
                    'started_at',
                    'attempts',
                    'error_message',
                    'message',
                    'updated_at',
                ]
            )

            actor = job.user or job.invoice.user

            ok, message = run_invoice_ocr_processing(
                job.invoice,
                actor,
                'OCR выполнен из очереди'
            )

            job.finished_at = timezone.now()

            if ok:

                job.status = OCRJob.STATUS_DONE
                job.message = message
                job.error_message = ''
                success_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'OK OCRJob #{job.id} invoice #{job.invoice_id}: {message}'
                    )
                )

            else:

                job.status = OCRJob.STATUS_ERROR
                job.error_message = message
                job.message = ''
                error_count += 1

                self.stdout.write(
                    self.style.ERROR(
                        f'ERROR OCRJob #{job.id} invoice #{job.invoice_id}: {message}'
                    )
                )

            job.save(
                update_fields=[
                    'status',
                    'message',
                    'error_message',
                    'finished_at',
                    'updated_at',
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово. Успешно: {success_count}. Ошибок: {error_count}.'
            )
        )
