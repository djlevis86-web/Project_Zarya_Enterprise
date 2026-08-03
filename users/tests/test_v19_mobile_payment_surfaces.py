from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class V19MobilePaymentSurfacesTests(SimpleTestCase):
    def setUp(self):
        self.base = Path(settings.BASE_DIR)

    def test_registry_history_template_exposes_semantic_mobile_labels(self):
        template = (
            self.base / "templates/invoices/payment_registry_history.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn(
            'class="table-responsive payment-registry-history-responsive"',
            template,
        )

        labels = (
            "№",
            "Название",
            "Статус",
            "Счетов",
            "Сумма",
            "Создал",
            "Дата создания",
            "Выгрузил",
            "Дата выгрузки",
            "Факт. оплата",
            "Действия",
        )
        for label in labels:
            with self.subTest(label=label):
                self.assertIn(f'data-label="{label}"', template)

        self.assertEqual(template.count('data-label="'), len(labels))

    def test_registry_history_css_converts_table_to_mobile_cards(self):
        css = (
            self.base / "static/css/components/tables.css"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("V19 mobile payment registry history cards", css)
        self.assertRegex(
            css,
            re.compile(
                r"@media\s*\(max-width:\s*760px\).*?"
                r"\.payment-registry-history-responsive\s*\{"
                r".*?overflow\s*:\s*visible"
                r".*?\.payment-registry-history-table\s*\{"
                r".*?min-width\s*:\s*0"
                r".*?\.payment-registry-history-table\s+thead\s*\{"
                r".*?display\s*:\s*none"
                r".*?content\s*:\s*attr\(data-label\)",
                flags=re.S,
            ),
        )
        self.assertIn('td[data-label="Действия"] .btn', css)

    def test_payment_schedule_submit_owns_full_mobile_grid_row(self):
        css = (
            self.base / "static/css/components/documents-payments-workspace.css"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("V19 mobile payment schedule filter action", css)
        submit_rule = re.search(
            r"\.enterprise-schedule-filters\s*>\s*"
            r"\.btn\[type=\"submit\"\]\s*\{"
            r"(?P<body>[^}]*)\}",
            css,
            flags=re.S,
        )
        self.assertIsNotNone(submit_rule)
        body = submit_rule.group("body")
        self.assertRegex(body, r"width\s*:\s*100%")
        self.assertRegex(body, r"white-space\s*:\s*nowrap")
        self.assertRegex(body, r"word-break\s*:\s*keep-all")

    def test_mobile_contract_avoids_css_patch_techniques(self):
        tables_css = (
            self.base / "static/css/components/tables.css"
        ).read_text(encoding="utf-8-sig")
        workspace_css = (
            self.base / "static/css/components/documents-payments-workspace.css"
        ).read_text(encoding="utf-8-sig")

        registry_block = tables_css.split(
            "V19 mobile payment registry history cards", 1
        )[1]
        schedule_block = workspace_css.split(
            "V19 mobile payment schedule filter action", 1
        )[1]

        for block in (registry_block, schedule_block):
            self.assertNotIn("!important", block)
            self.assertNotIn("nth-child(", block)
            self.assertNotIn("overflow-x: auto", block)
