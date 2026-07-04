import json
from pathlib import Path

from django.conf import settings
from django.utils.dateparse import parse_datetime


INVOICE_BOT_REPORT_PATH = (
    Path("var")
    / "invoice_bot"
    / "latest_report.json"
)

REPORT_COUNT_FIELDS = (
    "total_count",
    "without_planned_payment_date_count",
    "without_counterparty_count",
    "unverified_amount_count",
    "without_ocr_text_count",
    "ready_for_registry_count",
    "not_ready_for_registry_count",
)


def get_invoice_bot_report_path():
    return (
        Path(settings.BASE_DIR)
        / INVOICE_BOT_REPORT_PATH
    )


def read_latest_invoice_bot_report():
    report_path = get_invoice_bot_report_path()

    if not report_path.exists():
        return None

    try:
        report = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    if not isinstance(
        report,
        dict
    ):
        return None

    for field_name in REPORT_COUNT_FIELDS:
        report[field_name] = _safe_int(
            report.get(
                field_name
            )
        )

    generated_at = report.get(
        "generated_at"
    )

    report["generated_at_datetime"] = None

    if generated_at:
        report["generated_at_datetime"] = parse_datetime(
            generated_at
        )

    return report


def _safe_int(value):
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0
