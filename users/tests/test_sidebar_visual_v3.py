from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


class SidebarVisualV3Tests(
    SimpleTestCase
):
    repo_root = Path(
        __file__
    ).resolve().parents[2]

    template_path = (
        repo_root
        / "templates"
        / "base.html"
    )

    sprite_path = (
        repo_root
        / "templates"
        / "components"
        / "sidebar_icon_sprite_v3.html"
    )

    brand_asset_path = (
        repo_root
        / "static"
        / "images"
        / "brand"
        / "zarya-logo-v1.webp"
    )

    css_path = (
        repo_root
        / "static"
        / "css"
        / "features"
        / "sidebar-visual-v3.css"
    )

    tokens_path = (
        repo_root
        / "static"
        / "css"
        / "base"
        / "variables.css"
    )

    state_script_path = (
        repo_root
        / "static"
        / "js"
        / "sidebar-state-v3.js"
    )

    tooltip_script_path = (
        repo_root
        / "static"
        / "js"
        / "sidebar-tooltip-v3.js"
    )

    app_path = (
        repo_root
        / "static"
        / "css"
        / "app.css"
    )

    import_value = (
        "./features/"
        "sidebar-visual-v3.css"
    )

    def test_template_uses_local_svg_icon_system(
        self,
    ) -> None:
        template_text = (
            self.template_path.read_text(
                encoding="utf-8-sig",
            )
        )

        required_markers = (
            'data-sidebar-version="v3"',
            'sidebar_icon_sprite_v3.html',
            'js/sidebar-state-v3.js',
            'js/sidebar-mobile-drawer.js',
            'js/sidebar-tooltip-v3.js',
            'id="sidebar-desktop-toggle"',
            'id="sidebar-mobile-toggle"',
            'class="sidebar-mobile-backdrop"',
            'class="sidebar-brand-copy"',
            'class="brand-mark-image"',
            'class="nav-label"',
            'images/brand/zarya-logo-v1.webp',
            'href="#z-icon-dashboard"',
            'href="#z-icon-file-text"',
            'href="#z-icon-upload-cloud"',
            'href="#z-icon-history"',
            'href="#z-icon-calendar-clock"',
            'href="#z-icon-wallet"',
            'href="#z-icon-building"',
            'href="#z-icon-circle-alert"',
            'href="#z-icon-shield-check"',
            'href="#z-icon-database-sync"',
            'href="#z-icon-settings"',
            'href="#z-icon-clipboard-list"',
            'href="#z-icon-users"',
            'href="#z-icon-shield"',
            'href="#z-icon-user"',
            'href="#z-icon-log-out"',
            'href="#z-icon-panel-close"',
            'href="#z-icon-menu"',
            'href="#z-icon-close"',
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    template_text,
                )

        self.assertEqual(
            template_text.count(
                'class="nav-icon"'
            ),
            16,
        )

        self.assertEqual(
            template_text.count(
                'class="nav-label"'
            ),
            16,
        )

        self.assertEqual(
            template_text.count(
                "<use "
            ),
            19,
        )

        self.assertNotIn(
            '<span class="nav-icon">',
            template_text,
        )

        for retired_reference in (
            "sidebar-fixed-left.css",
            "sidebar-collapsible-v1.css",
            "sidebar-collapsible-v1.js",
            "sidebar-floating-highlight.js",
        ):
            with self.subTest(
                retired_reference=retired_reference
            ):
                self.assertNotIn(
                    retired_reference,
                    template_text,
                )

    def test_approved_brand_asset_is_local(
        self,
    ) -> None:
        self.assertTrue(
            self.brand_asset_path.is_file()
        )

        self.assertGreater(
            self.brand_asset_path.stat().st_size,
            24_000,
        )

        self.assertLess(
            self.brand_asset_path.stat().st_size,
            120_000,
        )

        self.assertEqual(
            self.brand_asset_path.suffix,
            ".webp",
        )

    def test_sprite_contract_is_local_and_consistent(
        self,
    ) -> None:
        self.assertTrue(
            self.sprite_path.is_file()
        )

        sprite_text = (
            self.sprite_path.read_text(
                encoding="utf-8-sig",
            )
        )

        symbol_ids = re.findall(
            r'<symbol\s+id="([^"]+)"',
            sprite_text,
        )

        self.assertEqual(
            len(symbol_ids),
            20,
        )

        self.assertEqual(
            len(set(symbol_ids)),
            20,
        )

        self.assertEqual(
            sprite_text.count(
                'viewBox="0 0 24 24"'
            ),
            20,
        )

        self.assertIn(
            'xmlns="http://www.w3.org/2000/svg"',
            sprite_text,
        )

        external_resource_urls = re.findall(
            r'(?:href|src)="https?://[^"]+"',
            sprite_text,
        )

        self.assertEqual(
            external_resource_urls,
            [],
        )

        self.assertNotIn(
            "<script",
            sprite_text,
        )

    def test_visual_css_is_single_production_owner(
        self,
    ) -> None:
        self.assertTrue(
            self.css_path.is_file()
        )

        css_text = self.css_path.read_text(
            encoding="utf-8-sig",
        )

        required_markers = (
            "ОАО «Заря» — Sidebar Visual V3 + Brand Layer V1",
            "--zds-sidebar-width-expanded",
            "--zds-sidebar-width-collapsed",
            "--z-sidebar-current-width",
            "html.sidebar-is-collapsed",
            ".sidebar-brand-area",
            ".sidebar-brand-copy",
            ".sidebar .nav-link::before",
            ".sidebar .nav-link::after",
            ".brand-mark-image",
            ".sidebar-account-card",
            ".sidebar-tooltip-v3",
            "body.sidebar-mobile-open",
            "@media (min-width: 981px)",
            "@media (max-width: 980px)",
            "@media (max-width: 520px)",
            "@media (prefers-reduced-motion: reduce)",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    css_text,
                )

        self.assertEqual(
            css_text.count(
                "!important"
            ),
            0,
        )

        self.assertNotIn(
            ":has(",
            css_text,
        )

        self.assertNotRegex(
            css_text,
            r":nth-(?:child|of-type)\(",
        )

        self.assertNotRegex(
            css_text,
            (
                r"(?i)"
                r"(?:#[0-9a-f]{3,8}\b"
                r"|rgba?\s*\("
                r"|hsla?\s*\()"
            ),
        )

    def test_sidebar_tokens_cover_dark_and_light_themes(
        self,
    ) -> None:
        token_text = self.tokens_path.read_text(
            encoding="utf-8-sig",
        )

        required_tokens = (
            "--zds-sidebar-width-expanded",
            "--zds-sidebar-width-collapsed",
            "--zds-sidebar-drawer-width",
            "--zds-sidebar-surface",
            "--zds-sidebar-surface-raised",
            "--zds-sidebar-surface-hover",
            "--zds-sidebar-surface-active",
            "--zds-sidebar-border",
            "--zds-sidebar-border-active",
            "--zds-sidebar-text",
            "--zds-sidebar-text-muted",
            "--zds-sidebar-accent",
            "--zds-sidebar-danger",
            "--zds-sidebar-active-accent",
            "--zds-sidebar-logo-surface",
            "--zds-sidebar-shadow",
            "--zds-sidebar-tooltip-shadow",
        )

        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(
                    token,
                    token_text,
                )

        self.assertIn(
            "body.light-theme",
            token_text,
        )

    def test_state_script_preserves_behavior_and_semantics(
        self,
    ) -> None:
        self.assertTrue(
            self.state_script_path.is_file()
        )

        script_text = (
            self.state_script_path.read_text(
                encoding="utf-8-sig",
            )
        )

        required_markers = (
            "zarya.sidebar.collapsed.v1",
            "sidebar-is-collapsed",
            "data-sidebar-collapsed",
            "data-sidebar-ready",
            "sidebar-desktop-toggle",
            "(min-width: 981px)",
            "localStorage",
            "aria-expanded",
            "aria-current",
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

    def test_tooltip_script_uses_accessible_portal(
        self,
    ) -> None:
        self.assertTrue(
            self.tooltip_script_path.is_file()
        )

        script_text = (
            self.tooltip_script_path.read_text(
                encoding="utf-8-sig",
            )
        )

        required_markers = (
            "sidebar-tooltip-v3",
            'setAttribute(\n            "role",\n            "tooltip"',
            "aria-describedby",
            "data-sidebar-label",
            "sidebar-is-collapsed",
            "getBoundingClientRect",
            "MutationObserver",
            "Escape",
            "resize",
            "scroll",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    script_text,
                )

    def test_app_import_contract_places_v3_last(
        self,
    ) -> None:
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

        self.assertNotIn(
            "./features/sidebar-fixed-left.css",
            imports,
        )

        self.assertNotIn(
            "./features/sidebar-collapsible-v1.css",
            imports,
        )

    def test_retired_sidebar_layers_are_removed(
        self,
    ) -> None:
        retired_paths = (
            self.repo_root
            / "static"
            / "css"
            / "features"
            / "sidebar-fixed-left.css",
            self.repo_root
            / "static"
            / "css"
            / "features"
            / "sidebar-collapsible-v1.css",
            self.repo_root
            / "static"
            / "js"
            / "sidebar-collapsible-v1.js",
            self.repo_root
            / "static"
            / "js"
            / "sidebar-floating-highlight.js",
        )

        for retired_path in retired_paths:
            with self.subTest(
                retired_path=str(
                    retired_path
                )
            ):
                self.assertFalse(
                    retired_path.exists()
                )
