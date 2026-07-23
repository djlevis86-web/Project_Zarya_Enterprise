from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DashboardLatestDocumentsTests(SimpleTestCase):
    def test_latest_documents_use_semantic_structure_and_keep_routes(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dashboard.html"
        )

        template = template_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        expected_counts = {
            "dashboard-latest-panel-v1": 1,
            "dashboard-latest-scroll-v1": 1,
            "dashboard-latest-row-v1": 1,
            "dashboard-latest-title-v1": 1,
            "dashboard-latest-table": 1,
            "{% for invoice in latest_invoices %}": 1,
        }

        for token, expected_count in expected_counts.items():
            with self.subTest(
                token=token
            ):
                self.assertEqual(
                    template.count(token),
                    expected_count,
                )

        self.assertNotIn(
            '</div><div class="card">',
            template,
        )

        panel_start = template.index(
            (
                '<div class="card '
                'dashboard-latest-panel-v1">'
            )
        )

        title_position = template.index(
            "dashboard-latest-title-v1",
            panel_start,
        )

        scroll_position = template.index(
            "dashboard-latest-scroll-v1",
            title_position,
        )

        table_position = template.index(
            "dashboard-latest-table",
            scroll_position,
        )

        loop_position = template.index(
            "{% for invoice in latest_invoices %}",
            table_position,
        )

        row_position = template.index(
            (
                '<tr class="'
                'dashboard-latest-row-v1">'
            ),
            loop_position,
        )

        self.assertLess(
            panel_start,
            title_position,
        )

        self.assertLess(
            title_position,
            scroll_position,
        )

        self.assertLess(
            scroll_position,
            table_position,
        )

        self.assertLess(
            table_position,
            loop_position,
        )

        self.assertLess(
            loop_position,
            row_position,
        )

        endblock_position = template.index(
            "{% endblock %}",
            loop_position,
        )

        latest_block = template[
            panel_start:endblock_position
        ]

        self.assertEqual(
            latest_block.count(
                "{% url 'invoice_list' %}"
            ),
            1,
        )

        self.assertEqual(
            latest_block.count(
                (
                    "{% url 'invoice_detail' "
                    "invoice.id %}"
                )
            ),
            2,
        )

        self.assertEqual(
            latest_block.count(
                (
                    "status-badge "
                    "status-{{ invoice.status }}"
                )
            ),
            1,
        )

        header_match = re.search(
            (
                r'<table[^>]*dashboard-latest-table'
                r'[^>]*>.*?<thead>(.*?)</thead>'
            ),
            latest_block,
            flags=re.DOTALL,
        )

        self.assertIsNotNone(
            header_match
        )

        if header_match is None:
            self.fail(
                "Latest table header was not found."
            )

        header_cells = re.findall(
            r"<th[^>]*>(.*?)</th>",
            header_match.group(1),
            flags=re.DOTALL,
        )

        header_labels = [
            " ".join(
                re.sub(
                    r"<[^>]+>",
                    " ",
                    cell,
                ).split()
            )
            for cell in header_cells
        ]

        self.assertEqual(
            header_labels,
            [
                "ID",
                "Документ",
                "Сумма",
                "Статус",
                "Действие",
            ],
        )

    def test_latest_documents_visual_layer_is_page_scoped(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dashboard.html"
        )

        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "dashboard.css"
        )

        template = template_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        css = css_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        expected_template_tokens = {
            (
                'dashboard-latest-table" '
                'aria-label="Последние документы"'
            ): 1,
            "dashboard-latest-id-v1": 1,
            "dashboard-latest-document-v1": 1,
            "dashboard-latest-amount-v1": 1,
            "dashboard-latest-status-v1": 1,
            "dashboard-latest-action-v1": 1,
            'data-label="ID"': 1,
            'data-label="Документ"': 1,
            'data-label="Сумма"': 1,
            'data-label="Статус"': 1,
            'data-label="Действие"': 1,
        }

        for token, expected_count in (
            expected_template_tokens.items()
        ):
            with self.subTest(
                token=token
            ):
                self.assertEqual(
                    template.count(token),
                    expected_count,
                )

        start_marker = (
            "/* DASHBOARD-LATEST-UX-"
            "PILOT-V1-START */"
        )

        end_marker = (
            "/* DASHBOARD-LATEST-UX-"
            "PILOT-V1-END */"
        )

        self.assertEqual(
            css.count(start_marker),
            1,
        )

        self.assertEqual(
            css.count(end_marker),
            1,
        )

        block_start = css.index(
            start_marker
        )

        block_end = (
            css.index(
                end_marker,
                block_start,
            )
            + len(end_marker)
        )

        pilot_css = css[
            block_start:block_end
        ]

        required_css_tokens = (
            (
                ".dashboard-page "
                ".dashboard-latest-panel-v1 {"
            ),
            (
                ".dashboard-page "
                ".dashboard-latest-scroll-v1 {"
            ),
            (
                ".dashboard-page "
                ".dashboard-latest-table {"
            ),
            "@media (max-width: 900px) {",
            "@media (max-width: 720px) {",
            "@media (max-width: 430px) {",
            "content: attr(data-label);",
            "grid-template-columns:",
            "font-variant-numeric: tabular-nums;",
        )

        for token in required_css_tokens:
            with self.subTest(
                token=token
            ):
                self.assertIn(
                    token,
                    pilot_css,
                )

        forbidden_css_tokens = (
            "\n.dashboard-latest-panel-v1 {",
            "\n.dashboard-latest-scroll-v1 {",
            "\n.dashboard-latest-table {",
            ":has(",
        )

        for token in forbidden_css_tokens:
            with self.subTest(
                token=token
            ):
                self.assertNotIn(
                    token,
                    pilot_css,
                )
