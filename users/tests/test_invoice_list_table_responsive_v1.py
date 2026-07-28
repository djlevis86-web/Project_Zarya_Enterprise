from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InvoiceListTableResponsiveV1Tests(
    SimpleTestCase
):
    import_line = (
        '@import "./features/'
        'invoice-list-table-responsive-v1.css";'
    )

    expected_zds_tokens = frozenset(
        {
            "--zds-color-border",
            "--zds-color-surface",
            "--zds-color-surface-elevated",
            "--zds-color-text",
            "--zds-color-text-muted",
            "--zds-control-height-default",
            "--zds-radius-control",
            "--zds-radius-panel",
            "--zds-shadow-card",
            "--zds-space-2",
            "--zds-space-4",
            "--zds-space-6",
        }
    )

    @staticmethod
    def normalize_text(
        path: Path,
    ) -> str:
        return path.read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

    def test_invoice_list_table_responsive_v1_contract(
        self,
    ):
        base_dir = Path(
            settings.BASE_DIR
        )

        app_path = (
            base_dir
            / "static"
            / "css"
            / "app.css"
        )

        responsive_path = (
            base_dir
            / "static"
            / "css"
            / "features"
            / "invoice-list-table-responsive-v1.css"
        )

        self.assertTrue(
            app_path.is_file()
        )

        self.assertTrue(
            responsive_path.is_file()
        )

        app_text = self.normalize_text(
            app_path
        )

        responsive_text = self.normalize_text(
            responsive_path
        )

        imports = re.findall(
            (
                r"@import\s+"
                r"(?:url\(\s*)?"
                r"[\"']([^\"']+)[\"']"
                r"\s*\)?\s*;"
            ),
            app_text,
            flags=re.IGNORECASE,
        )

        self.assertEqual(
            len(imports),
            38,
        )

        self.assertEqual(
            imports[-1],
            (
                "./features/"
                "sidebar-visual-v3.css"
            ),
        )

        self.assertEqual(
            app_text.count(
                self.import_line
            ),
            1,
        )

        # CSS @import rules must stay before every style rule.
        app_without_comments = re.sub(
            r"/\*.*?\*/",
            "",
            app_text,
            flags=re.DOTALL,
        )

        import_rule_pattern = (
            r"@import\s+"
            r"(?:url\(\s*)?"
            r"[\"']([^\"']+)[\"']"
            r"\s*\)?\s*;"
        )

        import_rule_matches = list(
            re.finditer(
                import_rule_pattern,
                app_without_comments,
                flags=re.IGNORECASE,
            )
        )

        self.assertEqual(
            len(import_rule_matches),
            38,
        )

        import_prelude = app_without_comments[
            : import_rule_matches[-1].end()
        ]

        non_import_prelude = re.sub(
            import_rule_pattern,
            "",
            import_prelude,
            flags=re.IGNORECASE,
        ).strip()

        self.assertEqual(
            non_import_prelude,
            "",
        )

        self.assertEqual(
            responsive_text.count(
                (
                    "/* "
                    "INVOICE-LIST-TABLE-RESPONSIVE-V1-START "
                    "*/"
                )
            ),
            1,
        )

        self.assertEqual(
            responsive_text.count(
                (
                    "/* "
                    "INVOICE-LIST-TABLE-RESPONSIVE-V1-END "
                    "*/"
                )
            ),
            1,
        )

        required_fragments = (
            ".invoice-list-table-panel-v1 {",
            ".invoice-list-table-scroll-v1 {",
            ".invoice-list-table-v1 {",
            ".invoice-list-table-v1 .col-select {",
            ".invoice-list-table-v1 .col-actions {",
            (
                ".invoice-list-table-v1 "
                ".invoice-list-table-row-v1 {"
            ),
            (
                ".invoice-list-table-v1 "
                ".invoice-list-table-row-v1 > td::before {"
            ),
            (
                ".invoice-list-table-v1 "
                ".invoice-list-table-cell-document-v1::before {"
            ),
            (
                ".invoice-list-table-v1 "
                ".invoice-list-table-cell-actions-v1::before {"
            ),
            (
                ".invoice-list-table-v1 tbody > "
                "tr:not(.invoice-list-table-row-v1) > td[colspan] {"
            ),
            "@media (min-width: 75.0625rem) {",
            "/* INVOICE-LIST-TABLE-DESKTOP-FIT-V1-START */",
            "/* INVOICE-LIST-TABLE-DESKTOP-FIT-V1-END */",
            "width: 4.5% !important;",
            "width: 5.5% !important;",
            "width: 21% !important;",
            "width: 18% !important;",
            "width: 9% !important;",
            "width: 11% !important;",
            "width: 15% !important;",
            "width: 16% !important;",
            "@media (max-width: 75rem) {",
            "@media (max-width: 45rem) {",
            "@media (max-width: 26.875rem) {",
            'content: "Документ";',
            'content: "Поставщик / контрагент";',
            'content: "Сумма / OCR";',
            'content: "Статус";',
            'content: "Оплата";',
            'content: "Действия";',
        )

        for fragment in required_fragments:
            with self.subTest(
                fragment=fragment,
            ):
                self.assertIn(
                    fragment,
                    responsive_text,
                )

        actual_zds_tokens = frozenset(
            re.findall(
                (
                    r"var\("
                    r"(--zds-[A-Za-z0-9_-]+)"
                    r"\)"
                ),
                responsive_text,
            )
        )

        self.assertEqual(
            actual_zds_tokens,
            self.expected_zds_tokens,
        )

        self.assertEqual(
            responsive_text.count(
                "!important"
            ),
            86,
        )

        self.assertNotIn(
            "var(--z-",
            responsive_text,
        )

        self.assertNotIn(
            ":has(",
            responsive_text,
        )

        self.assertNotIn(
            "nth-child(",
            responsive_text,
        )

        self.assertNotIn(
            "data-label",
            responsive_text,
        )

        hardcoded_colors = re.findall(
            (
                r"#[0-9a-fA-F]{3,8}\b"
                r"|rgba?\([^)]*\)"
                r"|hsla?\([^)]*\)"
            ),
            responsive_text,
        )

        self.assertEqual(
            hardcoded_colors,
            [],
        )

        generic_patterns = (
            (
                r"(?<![A-Za-z0-9_-])"
                r"\.invoice-table"
                r"(?![A-Za-z0-9_-])"
            ),
            (
                r"(?<![A-Za-z0-9_-])"
                r"\.registry-table"
                r"(?![A-Za-z0-9_-])"
            ),
            (
                r"(?<![A-Za-z0-9_-])"
                r"\.table-scroll"
                r"(?![A-Za-z0-9_-])"
            ),
        )

        for pattern in generic_patterns:
            with self.subTest(
                pattern=pattern,
            ):
                self.assertIsNone(
                    re.search(
                        pattern,
                        responsive_text,
                    )
                )

        self.assertEqual(
            responsive_text.count(
                "grid-area:"
            ),
            8,
        )

        self.assertEqual(
            responsive_text.count(
                "td[colspan]"
            ),
            2,
        )
