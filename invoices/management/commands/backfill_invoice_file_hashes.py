import hashlib

from django.core.management.base import BaseCommand

from invoices.models import Invoice


class Command(BaseCommand):
    help = 'Заполняет file_hash для уже загруженных счетов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Пересчитать file_hash даже если он уже заполнен'
        )

    def calculate_file_hash(self, invoice):
        hasher = hashlib.sha256()

        invoice.file.open('rb')

        try:
            for chunk in invoice.file.chunks():
                hasher.update(chunk)
        finally:
            invoice.file.close()

        return hasher.hexdigest()

    def handle(self, *args, **options):
        force = options['force']

        if force:
            invoices = Invoice.objects.exclude(
                file=''
            )
        else:
            invoices = (
                Invoice.objects
                .exclude(file='')
                .filter(file_hash='')
            )

        total = invoices.count()

        updated = 0
        skipped = 0
        errors = 0

        self.stdout.write(
            self.style.NOTICE(
                f'Найдено счетов для обработки: {total}'
            )
        )

        for invoice in invoices.iterator():

            if not invoice.file:
                skipped += 1
                continue

            try:
                file_hash = self.calculate_file_hash(
                    invoice
                )

                invoice.file_hash = file_hash

                invoice.save(
                    update_fields=[
                        'file_hash'
                    ]
                )

                updated += 1

                self.stdout.write(
                    f'OK invoice #{invoice.id}: {file_hash}'
                )

            except Exception as error:
                errors += 1

                self.stdout.write(
                    self.style.WARNING(
                        f'ERROR invoice #{invoice.id}: {error}'
                    )
                )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Готово. Обновлено: {updated}, пропущено: {skipped}, ошибок: {errors}'
            )
        )