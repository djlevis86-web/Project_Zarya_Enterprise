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
            '<div class="card registry-filter-card">',
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
