import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from invoices.bot_report_services import (
    build_live_invoice_bot_report,
)


DEFAULT_REPORT_PATH = Path("var") / "invoice_bot" / "latest_report.json"


class Command(BaseCommand):
    help = "Запускает безопасный аудит документов к оплате без изменения данных"

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
        report = build_live_invoice_bot_report()
        report["mode"] = "audit_only"

        total_count = report["total_count"]
        without_planned_payment_date_count = report[
            "without_planned_payment_date_count"
        ]
        without_vendor_count = report[
            "without_vendor_count"
        ]
        without_counterparty_count = report[
            "without_counterparty_count"
        ]
        waiting_1c_sync_count = report[
            "waiting_1c_sync_count"
        ]
        counterparty_action_required_count = report[
            "counterparty_action_required_count"
        ]
        unverified_amount_count = report[
            "unverified_amount_count"
        ]
        without_ocr_text_count = report[
            "without_ocr_text_count"
        ]
        unknown_document_type_count = report[
            "unknown_document_type_count"
        ]
        ready_for_registry_count = report[
            "ready_for_registry_count"
        ]
        not_ready_for_registry_count = report[
            "not_ready_for_registry_count"
        ]

        self.stdout.write(
            "Invoice Bot Report"
        )
        self.stdout.write(
            "=================="
        )
        self.stdout.write(
            f"Всего активных документов: {total_count}"
        )
        self.stdout.write(
            ""
        )
        self.stdout.write(
            "Технический аудит"
        )
        self.stdout.write(
            "-----------------"
        )
        self.stdout.write(
            f"Без OCR-текста: {without_ocr_text_count}"
        )
        self.stdout.write(
            f"Неизвестный тип документа: {unknown_document_type_count}"
        )
        self.stdout.write(
            f"Без заполненного поставщика: {without_vendor_count}"
        )
        self.stdout.write(
            f"Без контрагента: {without_counterparty_count}"
        )
        self.stdout.write(
            f"Требуют проверки контрагента: {counterparty_action_required_count}"
        )
        self.stdout.write(
            f"Ожидают синхронизацию справочника 1С: {waiting_1c_sync_count}"
        )
        self.stdout.write(
            ""
        )
        self.stdout.write(
            "Рабочая очередь пользователя"
        )
        self.stdout.write(
            "--------------------------"
        )
        self.stdout.write(
            f"Без плановой даты оплаты: {without_planned_payment_date_count}"
        )
        self.stdout.write(
            f"Сумма ожидает подтверждения: {unverified_amount_count}"
        )
        self.stdout.write(
            f"Готовы к реестру оплаты: {ready_for_registry_count}"
        )
        self.stdout.write(
            f"Не готовы к реестру оплаты: {not_ready_for_registry_count}"
        )
        self.stdout.write(
            ""
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
