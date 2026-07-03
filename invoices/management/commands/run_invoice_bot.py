from django.core.management.base import BaseCommand
from django.db.models import Q

from invoices.models import Invoice
from invoices.payment_registry_services import validate_invoice_for_payment_registry


class Command(BaseCommand):
    help = "Запускает безопасный аудит счетов без изменения данных"

    def handle(self, *args, **options):
        invoices = (
            Invoice.objects
            .select_related(
                "counterparty",
            )
            .filter(
                is_deleted=False,
            )
        )

        total_count = invoices.count()

        without_planned_payment_date_count = invoices.filter(
            planned_payment_date__isnull=True,
        ).count()

        without_counterparty_count = invoices.filter(
            counterparty__isnull=True,
        ).count()

        unverified_amount_count = invoices.filter(
            amount_verified=False,
        ).count()

        without_ocr_text_count = invoices.filter(
            Q(ocr_text__isnull=True)
            |
            Q(ocr_text="")
        ).count()

        ready_for_registry_count = 0
        not_ready_for_registry_count = 0

        for invoice in invoices:
            errors, warnings = validate_invoice_for_payment_registry(
                invoice
            )

            if errors:
                not_ready_for_registry_count += 1
            else:
                ready_for_registry_count += 1

        self.stdout.write(
            "Invoice Bot Report"
        )
        self.stdout.write(
            "=================="
        )
        self.stdout.write(
            f"Всего активных счетов: {total_count}"
        )
        self.stdout.write(
            f"Без плановой даты оплаты: {without_planned_payment_date_count}"
        )
        self.stdout.write(
            f"Без контрагента: {without_counterparty_count}"
        )
        self.stdout.write(
            f"С неподтверждённой суммой: {unverified_amount_count}"
        )
        self.stdout.write(
            f"Без OCR-текста: {without_ocr_text_count}"
        )
        self.stdout.write(
            f"Готовы к реестру оплаты: {ready_for_registry_count}"
        )
        self.stdout.write(
            f"Не готовы к реестру оплаты: {not_ready_for_registry_count}"
        )
        self.stdout.write(
            "Режим: только аудит, без изменения данных"
        )
