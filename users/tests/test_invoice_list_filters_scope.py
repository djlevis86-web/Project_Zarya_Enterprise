from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InvoiceListFiltersScopeTests(
    SimpleTestCase
):
    def test_filter_scope_preserves_existing_contract(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "invoices"
            / "invoice_list.html"
        )

        template = template_path.read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        expected_token_counts = {
            "invoice-list-filter-panel-v1": 1,
            "invoice-list-filters-v1": 1,
            "invoice-list-recent-filters-v1": 1,
            "invoice-filter-clean-v5": 1,
            "invoice-filter-actions-v5": 1,
            "invoice-recent-filters-v1": 1,
            "registry-filter-card": 1,
        }

        for token, expected_count in (
            expected_token_counts.items()
        ):
            with self.subTest(
                token=token
            ):
                self.assertEqual(
                    template.count(token),
                    expected_count,
                )

        filter_start = template.index(
            "invoice-list-filter-panel-v1"
        )

        table_wrap = template.index(
            "invoice-table-wrap"
        )

        table_card_start = template.rfind(
            '<div class="card',
            filter_start,
            table_wrap,
        )

        self.assertGreater(
            table_card_start,
            filter_start,
        )

        filter_block = template[
            filter_start:table_card_start
        ]

        self.assertEqual(
            len(
                re.findall(
                    r"<form\b",
                    filter_block,
                )
            ),
            2,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<input\b",
                    filter_block,
                )
            ),
            5,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<select\b",
                    filter_block,
                )
            ),
            5,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<button\b",
                    filter_block,
                )
            ),
            2,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<a\b",
                    filter_block,
                )
            ),
            2,
        )

        field_names = tuple(
            re.findall(
                r'\bname="([^"]+)"',
                filter_block,
            )
        )

        field_ids = tuple(
            re.findall(
                r'\bid="([^"]+)"',
                filter_block,
            )
        )

        routes = tuple(
            re.findall(
                r"{%\s+url\s+'([^']+)'",
                filter_block,
            )
        )

        self.assertEqual(
            field_names,
            (
                "search",
                "user",
                "status",
                "payment_status",
                "document_type",
                "document_date_from",
                "document_date_to",
                "planned_payment_date_from",
                "planned_payment_date_to",
                "sort",
            ),
        )

        self.assertEqual(
            field_ids,
            (
                "invoice_search",
                "invoice_user",
                "invoice_status",
                "payment_status",
                "document_type",
                "document_date_from",
                "document_date_to",
                "planned_payment_date_from",
                "planned_payment_date_to",
                "invoice_sort",
            ),
        )

        self.assertEqual(
            routes,
            (
                "invoice_list",
                "invoice_list",
                "clear_recent_invoice_filters",
            ),
        )

        self.assertLess(
            template.index(
                "invoice-list-filter-panel-v1"
            ),
            template.index(
                "invoice-list-filters-v1"
            ),
        )

        self.assertLess(
            template.index(
                "invoice-list-filters-v1"
            ),
            template.index(
                "invoice-list-recent-filters-v1"
            ),
        )

        self.assertLess(
            template.index(
                "invoice-list-recent-filters-v1"
            ),
            table_card_start,
        )

        self.assertNotIn(
            'style="',
            filter_block,
        )

        self.assertNotIn(
            "onsubmit=",
            filter_block,
        )

    def test_filter_visual_layer_is_page_scoped(
        self,
    ):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "invoice-list.css"
        )

        app_css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "app.css"
        )

        css = css_path.read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        app_css = app_css_path.read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        start_marker = (
            "/* INVOICE-LIST-FILTERS-"
            "UX-PILOT-V1-START */"
        )

        end_marker = (
            "/* INVOICE-LIST-FILTERS-"
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

        start = css.index(
            start_marker
        )

        end = (
            css.index(
                end_marker,
                start,
            )
            + len(end_marker)
        )

        block = css[
            start:end
        ]

        required_tokens = (
            ".invoice-list-filter-panel-v1 {",
            ".invoice-list-filters-v1 {",
            ".filter-field:focus-within",
            ".invoice-list-recent-filters-v1 {",
            "@media (max-width: 1100px)",
            "@media (max-width: 720px)",
            "grid-column: 1 / -1 !important;",
            "grid-template-columns: 1fr !important;",
        )

        for token in required_tokens:
            with self.subTest(
                token=token
            ):
                self.assertIn(
                    token,
                    block,
                )

        forbidden_tokens = (
            ".registry-filter-card",
            ".invoice-table",
            ".invoice-table-compact",
            ":has(",
        )

        for token in forbidden_tokens:
            with self.subTest(
                token=token
            ):
                self.assertNotIn(
                    token,
                    block,
                )

        page_import_position = (
            app_css.index(
                "./pages/invoice-list.css"
            )
        )

        late_filter_import_position = (
            app_css.index(
                "./features/ui-polish-filters.css"
            )
        )

        self.assertLess(
            page_import_position,
            late_filter_import_position,
        )

        self.assertGreaterEqual(
            block.count(
                ".invoice-list-filter-panel-v1"
            ),
            20,
        )
