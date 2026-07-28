from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PageHeaderVisualLayerV1Tests(
    SimpleTestCase
):
    import_line = (
        '@import "./features/'
        'page-header-visual-v1.css";'
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
            "--zds-touch-target-min",
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

    def test_page_header_visual_layer_v1_contract(
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

        visual_path = (
            base_dir
            / "static"
            / "css"
            / "features"
            / "page-header-visual-v1.css"
        )

        self.assertTrue(
            app_path.is_file()
        )

        self.assertTrue(
            visual_path.is_file()
        )

        app_text = self.normalize_text(
            app_path
        )

        visual_text = self.normalize_text(
            visual_path
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

        self.assertIn(
            (
                "./features/"
                "page-header-visual-v1.css"
            ),
            imports,
        )

        self.assertEqual(
            imports.count(
                (
                    "./features/"
                    "page-header-visual-v1.css"
                )
            ),
            1,
        )

        self.assertLess(
            imports.index(
                (
                    "./features/"
                    "ui-polish-actions.css"
                )
            ),
            imports.index(
                (
                    "./features/"
                    "page-header-visual-v1.css"
                )
            ),
        )

        self.assertLess(
            imports.index(
                (
                    "./features/"
                    "page-header-visual-v1.css"
                )
            ),
            imports.index(
                (
                    "./features/"
                    "invoice-list-table-responsive-v1.css"
                )
            ),
        )

        self.assertEqual(
            app_text.count(
                self.import_line
            ),
            1,
        )

        self.assertEqual(
            visual_text.count(
                (
                    "/* "
                    "PAGE-HEADER-VISUAL-V1-START "
                    "*/"
                )
            ),
            1,
        )

        self.assertEqual(
            visual_text.count(
                (
                    "/* "
                    "PAGE-HEADER-VISUAL-V1-END "
                    "*/"
                )
            ),
            1,
        )

        required_selectors = (
            ".page-header-v1 {",
            ".page-header-copy-v1 {",
            ".page-header-v1 .page-title {",
            ".page-header-v1 .page-subtitle {",
            ".page-header-actions-v1 {",
            ".page-header-actions-v1 > form {",
            ".page-header-actions-v1 .btn {",
            (
                ".invoice-list-header-v1 "
                ".page-header-actions-v1 {"
            ),
            "@media (max-width: 64rem) {",
            "@media (max-width: 45rem) {",
        )

        for selector in required_selectors:
            with self.subTest(
                selector=selector,
            ):
                self.assertIn(
                    selector,
                    visual_text,
                )

        actual_zds_tokens = frozenset(
            re.findall(
                (
                    r"var\("
                    r"(--zds-[A-Za-z0-9_-]+)"
                    r"\)"
                ),
                visual_text,
            )
        )

        self.assertEqual(
            actual_zds_tokens,
            self.expected_zds_tokens,
        )

        self.assertEqual(
            visual_text.count(
                "!important"
            ),
            29,
        )

        self.assertNotIn(
            "var(--z-",
            visual_text,
        )

        self.assertNotIn(
            ":has(",
            visual_text,
        )

        self.assertNotIn(
            "nth-child(",
            visual_text,
        )

        hardcoded_colors = re.findall(
            (
                r"#[0-9a-fA-F]{3,8}\b"
                r"|rgba?\([^)]*\)"
                r"|hsla?\([^)]*\)"
            ),
            visual_text,
        )

        self.assertEqual(
            hardcoded_colors,
            [],
        )

        generic_patterns = (
            (
                r"(?<![A-Za-z0-9_-])"
                r"\.page-header"
                r"(?![A-Za-z0-9_-])"
            ),
            (
                r"(?<![A-Za-z0-9_-])"
                r"\.registry-actions"
                r"(?![A-Za-z0-9_-])"
            ),
            (
                r"(?<![A-Za-z0-9_-])"
                r"\.page-actions"
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
                        visual_text,
                    )
                )
