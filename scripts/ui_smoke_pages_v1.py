import os
import sys
from pathlib import Path

import django
from django.test import Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model


BASE_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = BASE_DIR / "docs" / "UI_SMOKE_REPORT_RAW.md"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.local"
)

django.setup()


def check_response(label, route_name, client):
    try:
        url = reverse(route_name)
    except NoReverseMatch as exc:
        return {
            "label": label,
            "route": route_name,
            "url": "-",
            "status": "NO_REVERSE",
            "ok": False,
            "notes": str(exc),
        }

    response = client.get(
        url,
        HTTP_HOST="127.0.0.1"
    )

    text = response.content.decode(
        "utf-8",
        errors="ignore"
    )

    has_app_css = "app.css" in text
    has_layout = "app-layout" in text or "login-page" in text
    has_error = response.status_code >= 500

    return {
        "label": label,
        "route": route_name,
        "url": url,
        "status": response.status_code,
        "ok": response.status_code < 500,
        "notes": (
            f"app_css={has_app_css}; "
            f"layout_marker={has_layout}; "
            f"server_error={has_error}; "
            f"location={response.headers.get('Location')}"
        ),
    }


def main():
    User = get_user_model()

    routes = [
        "dashboard",
        "profile",
        "invoice_list",
        "upload_invoice",
        "upload_batches",
        "payment_schedule",
        "payment_registry",
        "counterparty_directory",
        "ocr_queue",
        "system_dashboard",
        "audit:audit_log_list",
        "user_admin_list",
    ]

    users = [
        ("admin", "bylevinskiy@yandex.ru"),
        ("finance", "sobenina@zarya35.ru"),
        ("uploader", "smolina@zarya35.ru"),
    ]

    rows = []

    public_client = Client(HTTP_HOST="127.0.0.1")
    public_client.raise_request_exception = False

    rows.append(
        check_response(
            "public",
            "login",
            public_client
        )
    )

    for label, email in users:
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            rows.append(
                {
                    "label": label,
                    "route": "-",
                    "url": "-",
                    "status": "USER_NOT_FOUND",
                    "ok": False,
                    "notes": email,
                }
            )
            continue

        client = Client(HTTP_HOST="127.0.0.1")
        client.raise_request_exception = False
        client.force_login(user)

        for route in routes:
            rows.append(
                check_response(
                    label,
                    route,
                    client
                )
            )

    report = []

    report.append("# UI Smoke Report")
    report.append("")
    report.append("| User | Route | URL | Status | OK | Notes |")
    report.append("|---|---|---|---:|---:|---|")

    for row in rows:
        report.append(
            f"| {row['label']} | `{row['route']}` | `{row['url']}` | "
            f"{row['status']} | {row['ok']} | {row['notes']} |"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print("UI smoke report created:")
    print(REPORT_PATH)

    failed = [
        row
        for row in rows
        if not row["ok"]
    ]

    print("Total checks:", len(rows))
    print("Failed checks:", len(failed))

    for row in failed:
        print(row)


if __name__ == "__main__":
    main()
