from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InvoiceListHeaderStatsTests(SimpleTestCase):
    def test_header_and_stats_use_page_specific_semantic_anchors(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "invoices"
            / "invoice_list.html"
        )

        template = template_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        expected_counts = {
            "invoice-list-header-v1": 1,
            "invoice-list-stats-v1": 1,
            "invoice-list-stat-card-v1": 4,
            "invoice-top-actions-v1": 1,
            "invoice-filter-clean-v5": 1,
            "invoice-table-compact": 1,
        }

        for token, expected_count in expected_counts.items():
            with self.subTest(
                token=token
            ):
                self.assertEqual(
                    template.count(token),
                    expected_count,
                )

        header_start = template.index(
            "invoice-list-header-v1"
        )

        stats_start = template.index(
            "invoice-list-stats-v1",
            header_start,
        )

        filter_start = template.index(
            "registry-filter-card",
            stats_start,
        )

        table_start = template.index(
            "invoice-table-compact",
            filter_start,
        )

        self.assertLess(
            header_start,
            stats_start,
        )

        self.assertLess(
            stats_start,
            filter_start,
        )

        self.assertLess(
            filter_start,
            table_start,
        )

        header_block = template[
            header_start:stats_start
        ]

        header_routes = re.findall(
            r"{%\s+url\s+'([^']+)'",
            header_block,
        )

        self.assertEqual(
            header_routes,
            [
                "upload_invoice",
                "payment_registry",
                "ocr_queue",
            ],
        )

        stats_block = template[
            stats_start:filter_start
        ]

        stat_labels = re.findall(
            (
                r'<div class="stat-label">\s*'
                r"(.*?)\s*</div>"
            ),
            stats_block,
            flags=re.DOTALL,
        )

        stat_labels = [
            " ".join(
                label.split()
            )
            for label in stat_labels
        ]

        self.assertEqual(
            stat_labels,
            [
                "Всего документов",
                "Новые",
                "В работе",
                "Оплачено",
            ],
        )

        self.assertEqual(
            stats_block.count(
                "invoice-list-stat-card-v1"
            ),
            4,
        )

    def test_header_and_stats_visual_layer_is_page_scoped(
        self,
    ):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "invoice-list.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        start_marker = (
            "/* INVOICE-LIST-HEADER-STATS-"
            "UX-PILOT-V1-START */"
        )

        end_marker = (
            "/* INVOICE-LIST-HEADER-STATS-"
            "UX-PILOT-V1-END */"
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

        required_tokens = (
            (
                ".page-header."
                "invoice-list-header-v1 {"
            ),
            (
                ".stats-grid."
                "invoice-list-stats-v1 {"
            ),
            (
                ".stat-card."
                "invoice-list-stat-card-v1 {"
            ),
            (
                ".invoice-list-header-v1 "
                ".invoice-top-actions-v1 {"
            ),
            (
                ".stat-card."
                "invoice-list-stat-card-v1::before {"
            ),
            (
                ".stat-card."
                "invoice-list-stat-card-v1"
                ":nth-child(4) {"
            ),
            "font-variant-numeric: tabular-nums;",
            "@media (max-width: 1280px) {",
            "@media (max-width: 1100px) {",
            "@media (max-width: 620px) {",
            "@media (max-width: 430px) {",
            "@media (max-width: 360px) {",
        )

        for token in required_tokens:
            with self.subTest(
                token=token
            ):
                self.assertIn(
                    token,
                    pilot_css,
                )

        forbidden_tokens = (
            "\n.page-header {",
            "\n.stats-grid {",
            "\n.stat-card {",
            ".registry-filter-card",
            ".invoice-filter-clean-v5",
            ".invoice-table-compact",
            ":has(",
        )

        for token in forbidden_tokens:
            with self.subTest(
                token=token
            ):
                self.assertNotIn(
                    token,
                    pilot_css,
                )
