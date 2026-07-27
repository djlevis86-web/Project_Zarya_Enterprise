from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


class DashboardPageHeaderVisualLayerV1Tests(
    SimpleTestCase
):
    repo_root = Path(
        __file__
    ).resolve().parents[2]

    app_path = (
        repo_root
        / "static"
        / "css"
        / "app.css"
    )

    tokens_path = (
        repo_root
        / "static"
        / "css"
        / "base"
        / "variables.css"
    )

    visual_path = (
        repo_root
        / "static"
        / "css"
        / "features"
        / "dashboard-page-header-visual-v1.css"
    )

    template_path = (
        repo_root
        / "templates"
        / "dashboard.html"
    )

    import_value = (
        "./features/"
        "dashboard-page-header-visual-v1.css"
    )

    required_selectors = (
        ".dashboard-page .dashboard-page-header-v1",
        ".dashboard-page .dashboard-page-header-copy-v1",
        ".dashboard-page .dashboard-page-header-kicker-v1",
        ".dashboard-page .dashboard-page-title-v1",
        ".dashboard-page .dashboard-page-subtitle-v1",
        ".dashboard-page .dashboard-page-header-actions-v1",
        ".dashboard-page .dashboard-page-header-summary-v1",
    )

    def test_dashboard_page_header_visual_layer_v1_contract(
        self,
    ) -> None:
        self.assertTrue(
            self.app_path.is_file()
        )

        self.assertTrue(
            self.tokens_path.is_file()
        )

        self.assertTrue(
            self.visual_path.is_file()
        )

        self.assertTrue(
            self.template_path.is_file()
        )

        app_text = self.app_path.read_text(
            encoding="utf-8-sig",
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
            imports.count(
                self.import_value
            ),
            1,
        )

        self.assertEqual(
            imports[-1],
            self.import_value,
        )

        self.assertLess(
            imports.index(
                (
                    "./features/"
                    "invoice-list-table-responsive-v1.css"
                )
            ),
            imports.index(
                self.import_value
            ),
        )

        visual_text = self.visual_path.read_text(
            encoding="utf-8-sig",
        )

        for selector in self.required_selectors:
            self.assertIn(
                selector,
                visual_text,
            )

        self.assertEqual(
            visual_text.count(
                "!important"
            ),
            0,
        )

        self.assertNotIn(
            ":has(",
            visual_text,
        )

        self.assertNotRegex(
            visual_text,
            r":nth-(?:child|of-type)\(",
        )

        self.assertNotRegex(
            visual_text,
            r"var\(\s*--z-(?!ds-)",
        )

        self.assertNotRegex(
            visual_text,
            (
                r"(?i)"
                r"(?:#[0-9a-f]{3,8}\b"
                r"|rgba?\s*\("
                r"|hsla?\s*\()"
            ),
        )

        defined_tokens = set(
            re.findall(
                r"(--zds-[a-z0-9-]+)\s*:",
                self.tokens_path.read_text(
                    encoding="utf-8-sig",
                ),
                flags=re.IGNORECASE,
            )
        )

        used_tokens = set(
            re.findall(
                r"var\(\s*(--zds-[a-z0-9-]+)",
                visual_text,
                flags=re.IGNORECASE,
            )
        )

        self.assertTrue(
            used_tokens
        )

        self.assertTrue(
            used_tokens.issubset(
                defined_tokens
            ),
            msg=(
                "Dashboard visual layer uses "
                "undefined ZDS tokens: "
                + ", ".join(
                    sorted(
                        used_tokens
                        - defined_tokens
                    )
                )
            ),
        )

        for media_query in (
            "@media (max-width: 80rem)",
            "@media (max-width: 45rem)",
            "@media (max-width: 22rem)",
        ):
            self.assertEqual(
                visual_text.count(
                    media_query
                ),
                1,
            )

        template_text = (
            self.template_path.read_text(
                encoding="utf-8-sig",
            )
        )

        for semantic_class in (
            "dashboard-page-header-v1",
            "dashboard-page-header-copy-v1",
            "dashboard-page-header-kicker-v1",
            "dashboard-page-title-v1",
            "dashboard-page-subtitle-v1",
            "dashboard-page-header-actions-v1",
            "dashboard-page-header-summary-v1",
        ):
            self.assertEqual(
                template_text.count(
                    semantic_class
                ),
                1,
            )
