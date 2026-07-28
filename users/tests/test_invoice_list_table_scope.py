from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InvoiceListTableScopeTests(SimpleTestCase):
    def test_invoice_list_table_has_semantic_eight_column_scope(
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

        structure_tokens = (
            "invoice-list-table-panel-v1",
            "invoice-list-table-form-v1",
            "invoice-list-table-header-v1",
            "invoice-list-table-bulk-actions-v1",
            "invoice-list-table-scroll-v1",
            "invoice-list-table-v1",
            "invoice-list-table-columns-v1",
            "invoice-list-table-row-v1",
        )

        header_tokens = (
            "invoice-list-table-head-select-v1",
            "invoice-list-table-head-id-v1",
            "invoice-list-table-head-document-v1",
            "invoice-list-table-head-counterparty-v1",
            "invoice-list-table-head-amount-v1",
            "invoice-list-table-head-status-v1",
            "invoice-list-table-head-payment-v1",
            "invoice-list-table-head-actions-v1",
        )

        cell_tokens = (
            "invoice-list-table-cell-select-v1",
            "invoice-list-table-cell-id-v1",
            "invoice-list-table-cell-document-v1",
            "invoice-list-table-cell-counterparty-v1",
            "invoice-list-table-cell-amount-v1",
            "invoice-list-table-cell-status-v1",
            "invoice-list-table-cell-payment-v1",
            "invoice-list-table-cell-actions-v1",
        )

        for token in (
            structure_tokens
            + header_tokens
            + cell_tokens
        ):
            with self.subTest(
                token=token
            ):
                self.assertEqual(
                    template.count(token),
                    1,
                )

        scope_position = template.index(
            "invoice-list-table-panel-v1"
        )

        panel_start = template.rfind(
            "<div",
            0,
            scope_position,
        )

        pagination_start = template.index(
            (
                "{% if page_obj.paginator."
                "num_pages > 1 %}"
            ),
            scope_position,
        )

        panel = template[
            panel_start:pagination_start
        ]

        self.assertEqual(
            panel.count(
                (
                    "table registry-table "
                    "invoice-table "
                    "invoice-table-compact "
                    "invoice-list-table-v1"
                )
            ),
            1,
        )

        colgroup_start = panel.index(
            (
                '<colgroup class="'
                'invoice-list-table-columns-v1">'
            )
        )

        colgroup_end = (
            panel.index(
                "</colgroup>",
                colgroup_start,
            )
            + len("</colgroup>")
        )

        colgroup = panel[
            colgroup_start:colgroup_end
        ]

        self.assertEqual(
            tuple(
                re.findall(
                    r'<col\s+class="([^"]+)"',
                    colgroup,
                )
            ),
            (
                "col-select",
                "col-id",
                "col-document",
                "col-counterparty",
                "col-amount",
                "col-status",
                "col-payment",
                "col-actions",
            ),
        )

        thead_start = panel.index(
            "<thead>"
        )

        thead_end = (
            panel.index(
                "</thead>",
                thead_start,
            )
            + len("</thead>")
        )

        thead = panel[
            thead_start:thead_end
        ]

        th_openings = re.findall(
            r"<th(?:\s[^>]*)?>",
            thead,
        )

        self.assertEqual(
            len(th_openings),
            8,
        )

        for index, token in enumerate(
            header_tokens
        ):
            with self.subTest(
                header_index=index + 1
            ):
                self.assertIn(
                    token,
                    th_openings[index],
                )

        visible_headers = []

        for raw_content in re.findall(
            r"<th(?:\s[^>]*)?>(.*?)</th>",
            thead,
            flags=re.DOTALL,
        ):
            content = re.sub(
                r"<[^>]+>",
                " ",
                raw_content,
            )

            content = " ".join(
                content.split()
            )

            if content:
                visible_headers.append(
                    content
                )

        self.assertEqual(
            visible_headers,
            [
                "ID",
                "Документ",
                "Поставщик / Контрагент",
                "Сумма / OCR",
                "Статус",
                "Оплата",
                "Действия",
            ],
        )

        row_start = panel.index(
            "{% for invoice in page_obj %}"
        )

        row_end = panel.index(
            "{% empty %}",
            row_start,
        )

        row_template = panel[
            row_start:row_end
        ]

        self.assertEqual(
            len(
                re.findall(
                    r"<tr(?:\s[^>]*)?>",
                    row_template,
                )
            ),
            1,
        )

        td_openings = re.findall(
            r"<td(?:\s[^>]*)?>",
            row_template,
        )

        self.assertEqual(
            len(td_openings),
            8,
        )

        for index, token in enumerate(
            cell_tokens
        ):
            with self.subTest(
                cell_index=index + 1
            ):
                self.assertIn(
                    token,
                    td_openings[index],
                )

        route_counts = {
            "bulk_repeat_ocr": 1,
            "unmatched_counterparties": 1,
            "counterparties_missing_requisites": 1,
            "enqueue_ocr_jobs": 1,
            "invoice_detail": 1,
            "invoice_assign_counterparty": 1,
            "delete_invoice": 1,
            "quick_update_invoice": 1,
        }

        for route_name, expected_count in (
            route_counts.items()
        ):
            with self.subTest(
                route_name=route_name
            ):
                self.assertEqual(
                    panel.count(
                        (
                            "{% url '"
                            + route_name
                            + "'"
                        )
                    ),
                    expected_count,
                )

        self.assertEqual(
            panel.count(
                'name="invoice_ids"'
            ),
            1,
        )

        self.assertEqual(
            panel.count(
                'name="planned_payment_date"'
            ),
            1,
        )

        self.assertEqual(
            panel.count(
                'name="status"'
            ),
            1,
        )

        self.assertEqual(
            panel.count(
                'colspan="8"'
            ),
            1,
        )

        self.assertEqual(
            panel.count(
                "invoice-payment-cell"
            ),
            1,
        )

        self.assertEqual(
            panel.count(
                "invoice-actions-cell"
            ),
            1,
        )

        for obsolete_token in (
            "invoice-payment-action-head",
            "invoice-payment-action-cell",
            "invoice-payment-action-wrap",
            "invoice-payment-side",
            "invoice-action-side",
        ):
            with self.subTest(
                obsolete_token=obsolete_token
            ):
                self.assertNotIn(
                    obsolete_token,
                    panel,
                )
