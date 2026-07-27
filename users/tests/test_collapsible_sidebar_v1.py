from pathlib import Path
import re

from django.conf import settings
from django.test import SimpleTestCase


class CollapsibleSidebarV1Tests(
    SimpleTestCase
):
    import_value = (
        "./features/"
        "sidebar-collapsible-v1.css"
    )

    def test_active_layout_contains_desktop_sidebar_contract(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "base.html"
        )

        template_text = template_path.read_text(
            encoding="utf-8"
        )

        required_markers = (
            'id="app-sidebar"',
            'id="sidebar-desktop-toggle"',
            'class="sidebar-desktop-toggle"',
            'aria-controls="app-sidebar"',
            'aria-expanded="true"',
            'data-sidebar-collapsed="false"',
            'data-collapse-label="Свернуть меню"',
            'data-expand-label="Развернуть меню"',
            "js/sidebar-collapsible-v1.js",
            "js/sidebar-mobile-drawer.js",
            'id="sidebar-mobile-toggle"',
            'class="sidebar-mobile-backdrop"',
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    template_text,
                )

        self.assertEqual(
            template_text.count(
                'id="sidebar-desktop-toggle"'
            ),
            1,
        )

        self.assertEqual(
            template_text.count(
                "js/sidebar-collapsible-v1.js"
            ),
            1,
        )

        self.assertLess(
            template_text.index(
                "js/sidebar-collapsible-v1.js"
            ),
            template_text.index(
                "css/app.css"
            ),
        )

    def test_collapsible_sidebar_css_contract(
        self,
    ):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "features"
            / "sidebar-collapsible-v1.css"
        )

        self.assertTrue(
            css_path.is_file()
        )

        css_text = css_path.read_text(
            encoding="utf-8"
        )

        required_markers = (
            "--z-sidebar-collapsed-width: 76px",
            "@media (min-width: 981px)",
            "html.sidebar-is-collapsed",
            "--z-sidebar-width:",
            "var(--z-sidebar-collapsed-width)",
            ".sidebar-desktop-toggle",
            ".sidebar .nav-link > span:last-child",
            ".sidebar-user-meta",
            ".sidebar-user-action > span:last-child",
            "@media (max-width: 980px)",
            "@media (prefers-reduced-motion: reduce)",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    css_text,
                )

        hardcoded_color_pattern = re.compile(
            (
                r"(?i)"
                r"(?:#[0-9a-f]{3,8}\b"
                r"|rgba?\s*\("
                r"|hsla?\s*\()"
            )
        )

        self.assertIsNone(
            hardcoded_color_pattern.search(
                css_text
            )
        )

        self.assertNotIn(
            ":has(",
            css_text,
        )

        self.assertNotRegex(
            css_text,
            r":nth-(?:child|of-type)\(",
        )

    def test_collapsible_sidebar_script_contract(
        self,
    ):
        script_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "sidebar-collapsible-v1.js"
        )

        self.assertTrue(
            script_path.is_file()
        )

        script_text = script_path.read_text(
            encoding="utf-8"
        )

        required_markers = (
            "zarya.sidebar.collapsed.v1",
            "sidebar-is-collapsed",
            "data-sidebar-collapsed",
            "sidebar-desktop-toggle",
            "(min-width: 981px)",
            "localStorage",
            "aria-expanded",
            "data-sidebar-label",
            'new Event("resize")',
            '"storage"',
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    script_text,
                )

        self.assertNotIn(
            "sidebar-mobile-open",
            script_text,
        )

    def test_app_import_contract_places_sidebar_last(
        self,
    ):
        app_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "app.css"
        )

        app_text = app_path.read_text(
            encoding="utf-8"
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
            39,
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
                    "dashboard-page-header-visual-v1.css"
                )
            ),
            imports.index(
                self.import_value
            ),
        )
