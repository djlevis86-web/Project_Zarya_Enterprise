import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from invoices.models import Invoice
from invoices.payment_registry_services import validate_invoice_for_payment_registry


DEFAULT_REPORT_PATH = Path("var") / "invoice_bot" / "latest_report.json"


class Command(BaseCommand):
    help = "Запускает безопасный аудит счетов без изменения данных"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="write_json",
            help="Сохранить последний отчёт бота в JSON-файл",
        )
        parser.add_argument(
            "--json-path",
            dest="json_path",
            default="",
            help="Путь к JSON-файлу отчёта. По умолчанию: var/invoice_bot/latest_report.json",
        )

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

        report = {
            "generated_at": timezone.now().isoformat(),
            "total_count": total_count,
            "without_planned_payment_date_count": without_planned_payment_date_count,
            "without_counterparty_count": without_counterparty_count,
            "unverified_amount_count": unverified_amount_count,
            "without_ocr_text_count": without_ocr_text_count,
            "ready_for_registry_count": ready_for_registry_count,
            "not_ready_for_registry_count": not_ready_for_registry_count,
            "mode": "audit_only",
        }

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

        if options["write_json"]:
            report_path = self._get_report_path(
                options["json_path"]
            )
            self._write_json_report(
                report_path,
                report,
            )

            self.stdout.write(
                f"JSON-отчёт сохранён: {report_path}"
            )

    def _get_report_path(self, json_path):
        if json_path:
            return Path(
                json_path
            )

        return (
            Path(settings.BASE_DIR)
            / DEFAULT_REPORT_PATH
        )

    def _write_json_report(self, report_path, report):
        report_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        report_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
