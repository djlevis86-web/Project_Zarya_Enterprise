from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


class DesignSystemFoundationV20Tests(
    SimpleTestCase
):
    repo_root = Path(
        __file__
    ).resolve().parents[2]

    variables_path = (
        repo_root
        / "static/css/base/variables.css"
    )
    app_css_path = (
        repo_root
        / "static/css/app.css"
    )
    base_template_path = (
        repo_root
        / "templates/base.html"
    )
    sprite_path = (
        repo_root
        / "templates/components/zds_icon_sprite_v1.html"
    )
    retired_sprite_path = (
        repo_root
        / "templates/components/sidebar_icon_sprite_v3.html"
    )
    docs_path = (
        repo_root
        / "docs/design-system-v20.md"
    )

    component_paths = {
        "icons": repo_root / "static/css/components/icons.css",
        "buttons": repo_root / "static/css/components/buttons.css",
        "badges": repo_root / "static/css/components/badges.css",
        "tables": repo_root / "static/css/components/tables.css",
        "filters": repo_root / "static/css/components/filters.css",
        "pagination": repo_root / "static/css/components/pagination.css",
    }

    def test_v2_tokens_are_exact_and_additive(self):
        variables = self.variables_path.read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        start_marker = (
            "/* DESIGN-SYSTEM-TOKENS-V2-START */"
        )
        end_marker = (
            "/* DESIGN-SYSTEM-TOKENS-V2-END */"
        )

        self.assertEqual(
            variables.count(start_marker),
            1,
        )
        self.assertEqual(
            variables.count(end_marker),
            1,
        )

        start = variables.index(start_marker)
        end = (
            variables.index(
                end_marker,
                start,
            )
            + len(end_marker)
        )
        block = variables[start:end]

        expected_tokens = {'--zds-color-neutral': '#9aa7a0', '--zds-color-neutral-soft': 'rgba(154, 167, 160, 0.14)', '--zds-color-neutral-border': 'rgba(154, 167, 160, 0.28)', '--zds-color-success-soft': 'rgba(57, 185, 106, 0.14)', '--zds-color-success-border': 'rgba(57, 185, 106, 0.36)', '--zds-color-warning-soft': 'rgba(229, 166, 50, 0.14)', '--zds-color-warning-border': 'rgba(229, 166, 50, 0.38)', '--zds-color-danger-soft': 'rgba(232, 103, 103, 0.14)', '--zds-color-danger-border': 'rgba(232, 103, 103, 0.38)', '--zds-color-info-soft': 'rgba(95, 159, 232, 0.14)', '--zds-color-info-border': 'rgba(95, 159, 232, 0.36)', '--zds-color-disabled': '#64748b', '--zds-color-disabled-soft': 'rgba(100, 116, 139, 0.14)', '--zds-button-height-large': '42px', '--zds-button-height-medium': '36px', '--zds-button-height-compact': '32px', '--zds-button-height-icon': '32px', '--zds-button-radius': '8px', '--zds-button-padding-large': '18px', '--zds-button-padding-medium': '14px', '--zds-button-padding-compact': '10px', '--zds-icon-size-compact': '16px', '--zds-icon-size-default': '18px', '--zds-icon-size-large': '20px', '--zds-icon-stroke-width': '1.8', '--zds-font-weight-medium': '500', '--zds-font-weight-semibold': '600', '--zds-font-weight-bold': '700', '--zds-motion-duration-fast': '120ms', '--zds-motion-duration-default': '160ms', '--zds-table-row-height-dense': '40px', '--zds-table-row-height-standard': '48px', '--zds-row-selected-surface': 'rgba(8, 122, 54, 0.18)', '--zds-row-selected-border': 'rgba(120, 196, 66, 0.42)', '--zds-row-overdue-surface': 'rgba(232, 103, 103, 0.10)', '--zds-row-overdue-border': 'rgba(232, 103, 103, 0.34)', '--zds-row-error-surface': 'rgba(232, 103, 103, 0.14)', '--zds-row-warning-surface': 'rgba(229, 166, 50, 0.12)', '--zds-row-disabled-opacity': '0.56', '--zds-filter-chip-height': '32px', '--zds-filter-control-height': '36px'}

        declarations = re.findall(
            (
                r"(--zds-[A-Za-z0-9_-]+)"
                r"\s*:\s*"
                r"([^;{}]+);"
            ),
            block,
        )

        actual_tokens = {
            name: " ".join(value.split())
            for name, value in declarations
        }

        self.assertEqual(
            actual_tokens,
            expected_tokens,
        )
        self.assertEqual(
            len(actual_tokens),
            41,
        )

        self.assertLess(
            variables.index(
                "DESIGN-SYSTEM-TOKENS-V1-END"
            ),
            variables.index(
                "DESIGN-SYSTEM-TOKENS-V2-START"
            ),
        )

    def test_global_icon_sprite_replaces_sidebar_only_owner(self):
        base_template = self.base_template_path.read_text(
            encoding="utf-8-sig"
        )
        sprite = self.sprite_path.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            'zds_icon_sprite_v1.html',
            base_template,
        )
        self.assertNotIn(
            'sidebar_icon_sprite_v3.html',
            base_template,
        )
        self.assertFalse(
            self.retired_sprite_path.exists()
        )

        symbol_ids = re.findall(
            r'<symbol\s+id="([^"]+)"',
            sprite,
        )

        self.assertEqual(
            len(symbol_ids),
            58,
        )
        self.assertEqual(
            len(set(symbol_ids)),
            58,
        )

        for symbol_id in (
            "z-icon-dashboard",
            "z-icon-calendar-clock",
            "z-icon-wallet",
            "z-icon-search",
            "z-icon-filter",
            "z-icon-eye",
            "z-icon-pencil",
            "z-icon-trash",
            "z-icon-check",
            "z-icon-warning",
            "z-icon-error",
            "z-icon-success",
            "z-icon-ruble",
            "z-icon-more",
        ):
            with self.subTest(symbol_id=symbol_id):
                self.assertIn(
                    symbol_id,
                    symbol_ids,
                )

        self.assertIn(
            'class="sidebar-icon-sprite-v3"',
            sprite,
        )
        self.assertIn(
            'data-zds-icon-sprite="v1"',
            sprite,
        )
        self.assertNotRegex(
            sprite,
            r'(?:href|src)="https?://',
        )
        self.assertNotIn(
            "<script",
            sprite,
        )

        icons_css = self.component_paths[
            "icons"
        ].read_text(
            encoding="utf-8-sig"
        )
        self.assertIn(
            ".sidebar-icon-sprite-v3 {",
            icons_css,
        )

        tables_css = self.component_paths[
            "tables"
        ].read_text(
            encoding="utf-8-sig"
        )
        self.assertLess(
            tables_css.index(
                "DESIGN-SYSTEM-V20-TABLES-END"
            ),
            tables_css.index(
                "V19 mobile payment registry history cards"
            ),
        )

    def test_app_imports_global_icons_before_buttons(self):
        app_css = self.app_css_path.read_text(
            encoding="utf-8-sig"
        )

        imports = re.findall(
            (
                r"@import\s+"
                r"(?:url\(\s*)?"
                r"[\"']([^\"']+)[\"']"
                r"\s*\)?\s*;"
            ),
            app_css,
            flags=re.IGNORECASE,
        )

        self.assertEqual(
            len(imports),
            40,
        )
        self.assertEqual(
            imports.count(
                "./components/icons.css"
            ),
            1,
        )
        self.assertLess(
            imports.index(
                "./components/icons.css"
            ),
            imports.index(
                "./components/buttons.css"
            ),
        )

    def test_canonical_component_owners_are_global(self):
        required_markers = {
            "icons": (
                ".zds-icon {",
                ".zds-icon--compact {",
                ".zds-icon--filled {",
            ),
            "buttons": (
                "DESIGN-SYSTEM-V20-BUTTONS-START",
                ".zds-button {",
                ".zds-button--primary {",
                ".zds-button--secondary {",
                ".zds-button--tertiary {",
                ".zds-button--danger {",
                ".zds-button--compact {",
                ".zds-button--icon {",
            ),
            "badges": (
                "DESIGN-SYSTEM-V20-BADGES-START",
                ".zds-badge {",
                ".zds-badge--success {",
                ".zds-badge--warning {",
                ".zds-badge--danger {",
                ".zds-badge--info {",
            ),
            "tables": (
                "DESIGN-SYSTEM-V20-TABLES-START",
                ".zds-table {",
                ".zds-row--selected {",
                ".zds-row--overdue {",
                ".zds-row--error {",
            ),
            "filters": (
                "DESIGN-SYSTEM-V20-FILTERS-START",
                ".zds-filter-bar {",
                ".zds-filter-chip {",
                ".zds-filter-actions {",
            ),
            "pagination": (
                "DESIGN-SYSTEM-V20-PAGINATION-START",
                ".zds-pagination {",
                ".zds-pagination__link",
                ".zds-pagination__current",
            ),
        }

        for owner, markers in required_markers.items():
            css = self.component_paths[owner].read_text(
                encoding="utf-8-sig"
            )

            for marker in markers:
                with self.subTest(
                    owner=owner,
                    marker=marker,
                ):
                    self.assertIn(
                        marker,
                        css,
                    )

    def test_new_component_blocks_avoid_patch_techniques(self):
        marker_pairs = {
            "buttons": (
                "DESIGN-SYSTEM-V20-BUTTONS-START",
                "DESIGN-SYSTEM-V20-BUTTONS-END",
            ),
            "badges": (
                "DESIGN-SYSTEM-V20-BADGES-START",
                "DESIGN-SYSTEM-V20-BADGES-END",
            ),
            "tables": (
                "DESIGN-SYSTEM-V20-TABLES-START",
                "DESIGN-SYSTEM-V20-TABLES-END",
            ),
            "filters": (
                "DESIGN-SYSTEM-V20-FILTERS-START",
                "DESIGN-SYSTEM-V20-FILTERS-END",
            ),
            "pagination": (
                "DESIGN-SYSTEM-V20-PAGINATION-START",
                "DESIGN-SYSTEM-V20-PAGINATION-END",
            ),
        }

        raw_color_pattern = re.compile(
            (
                r"(?i)"
                r"(?:#[0-9a-f]{3,8}\b"
                r"|rgba?\s*\("
                r"|hsla?\s*\()"
            )
        )

        for owner, marker_pair in marker_pairs.items():
            css = self.component_paths[owner].read_text(
                encoding="utf-8-sig"
            )
            start = css.index(marker_pair[0])
            end = (
                css.index(
                    marker_pair[1],
                    start,
                )
                + len(marker_pair[1])
            )
            block = css[start:end]

            with self.subTest(owner=owner):
                self.assertNotIn(
                    "!important",
                    block,
                )
                self.assertNotIn(
                    ":has(",
                    block,
                )
                self.assertNotRegex(
                    block,
                    r":nth-(?:child|of-type)\(",
                )
                self.assertNotRegex(
                    block,
                    raw_color_pattern,
                )

    def test_button_size_and_no_wrap_contract(self):
        css = self.component_paths["buttons"].read_text(
            encoding="utf-8-sig"
        )
        start = css.index(
            "DESIGN-SYSTEM-V20-BUTTONS-START"
        )
        end = css.index(
            "DESIGN-SYSTEM-V20-BUTTONS-END",
            start,
        )
        block = css[start:end]

        for marker in (
            "var(--zds-button-height-large)",
            "var(--zds-button-height-medium)",
            "var(--zds-button-height-compact)",
            "var(--zds-button-height-icon)",
            "white-space: nowrap;",
            "word-break: keep-all;",
        ):
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    block,
                )

    def test_design_system_spec_is_tracked_and_project_wide(self):
        docs = self.docs_path.read_text(
            encoding="utf-8-sig"
        )

        for marker in (
            "обязательный визуальный контракт всего Project Zarya",
            "Page-level CSS отвечает только за компоновку",
            "Основной стиль — двутонный",
            "Large: 42 px",
            "Medium: 36 px",
            "Compact: 32 px",
            "локальные копии глобальных компонентов",
            "V20.2B — График платежей",
            "V20.2C — Реестр оплаты",
        ):
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    docs,
                )

    def test_page_owners_do_not_own_canonical_api(self):
        page_root = (
            self.repo_root
            / "static/css/pages"
        )

        for page_css in sorted(
            page_root.glob("*.css")
        ):
            css = page_css.read_text(
                encoding="utf-8-sig"
            )

            for selector in (
                ".zds-button",
                ".zds-badge",
                ".zds-table",
                ".zds-filter-bar",
                ".zds-pagination",
            ):
                with self.subTest(
                    page_css=page_css.name,
                    selector=selector,
                ):
                    self.assertNotIn(
                        selector,
                        css,
                    )
