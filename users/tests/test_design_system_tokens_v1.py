from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DesignSystemTokensV1Tests(
    SimpleTestCase
):
    def test_canonical_design_tokens_v1_contract(
        self,
    ):
        variables_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "base"
            / "variables.css"
        )

        app_css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "app.css"
        )

        variables = variables_path.read_text(
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
            "/* DESIGN-SYSTEM-TOKENS-"
            "V1-START */"
        )

        end_marker = (
            "/* DESIGN-SYSTEM-TOKENS-"
            "V1-END */"
        )

        self.assertEqual(
            variables.count(start_marker),
            1,
        )

        self.assertEqual(
            variables.count(end_marker),
            1,
        )

        start = variables.index(
            start_marker
        )

        end = (
            variables.index(
                end_marker,
                start,
            )
            + len(end_marker)
        )

        token_block = variables[
            start:end
        ]

        expected_tokens = {'--zds-font-family-sans': 'var(--font-family-base)',
 '--zds-color-canvas': '#060b07',
 '--zds-color-canvas-deep': '#020603',
 '--zds-color-surface': '#101913',
 '--zds-color-surface-soft': '#152119',
 '--zds-color-surface-elevated': '#18271d',
 '--zds-color-surface-accent': '#0d2d1a',
 '--zds-color-control': '#0d1811',
 '--zds-color-control-hover': '#13251a',
 '--zds-color-text': '#f7faf5',
 '--zds-color-text-soft': '#cad6cc',
 '--zds-color-text-muted': '#94a49a',
 '--zds-color-text-on-accent': '#ffffff',
 '--zds-color-text-on-dark': '#f8faf8',
 '--zds-color-border': 'rgba(158, 177, 165, 0.18)',
 '--zds-color-border-strong': 'rgba(158, 177, 165, 0.32)',
 '--zds-color-border-brand': 'rgba(120, 196, 66, 0.36)',
 '--zds-color-border-dawn': 'rgba(227, 179, 65, 0.54)',
 '--zds-color-accent': 'var(--zarya-forest-700)',
 '--zds-color-accent-strong': 'var(--zarya-growth-500)',
 '--zds-color-accent-soft': 'rgba(8, 122, 54, 0.18)',
 '--zds-color-dawn': 'var(--zarya-dawn-500)',
 '--zds-color-dawn-soft': 'rgba(227, 179, 65, 0.16)',
 '--zds-color-success': '#39b96a',
 '--zds-color-warning': '#e5a632',
 '--zds-color-danger': '#e86767',
 '--zds-color-info': '#5f9fe8',
 '--zds-space-1': '4px',
 '--zds-space-2': '8px',
 '--zds-space-3': '12px',
 '--zds-space-4': '16px',
 '--zds-space-6': '24px',
 '--zds-space-8': '32px',
 '--zds-radius-badge': '8px',
 '--zds-radius-control': '10px',
 '--zds-radius-panel': '12px',
 '--zds-radius-card': '16px',
 '--zds-radius-pill': '999px',
 '--zds-control-height-compact': '40px',
 '--zds-control-height-default': '42px',
 '--zds-table-row-height-compact': '44px',
 '--zds-table-row-height-default': '48px',
 '--zds-touch-target-min': '40px',
 '--zds-shadow-card': '0 12px 28px rgba(1, 8, 4, 0.18)',
 '--zds-shadow-focus': '0 0 0 3px rgba(227, 179, 65, 0.26)',
 '--zds-sidebar-width-expanded': '280px',
 '--zds-sidebar-width-collapsed': '84px',
 '--zds-sidebar-drawer-width': '320px',
 '--zds-sidebar-surface': 'var(--zarya-forest-950)',
 '--zds-sidebar-surface-raised': 'var(--zarya-forest-900)',
 '--zds-sidebar-surface-soft': 'rgba(255, 255, 255, 0.045)',
 '--zds-sidebar-surface-hover': 'rgba(255, 255, 255, 0.075)',
 '--zds-sidebar-surface-active': 'rgba(8, 122, 54, 0.22)',
 '--zds-sidebar-border': 'rgba(181, 204, 189, 0.15)',
 '--zds-sidebar-border-strong': 'rgba(181, 204, 189, 0.28)',
 '--zds-sidebar-border-active': 'rgba(120, 196, 66, 0.42)',
 '--zds-sidebar-border-dawn': 'var(--zds-color-border-dawn)',
 '--zds-sidebar-text': '#f7faf5',
 '--zds-sidebar-text-soft': '#c7d4ca',
 '--zds-sidebar-text-muted': '#87988d',
 '--zds-sidebar-accent': 'var(--zarya-growth-500)',
 '--zds-sidebar-active-accent': 'var(--zarya-dawn-500)',
 '--zds-sidebar-danger': '#f1a0a0',
 '--zds-sidebar-logo-surface': 'var(--zarya-linen-50)',
 '--zds-sidebar-shadow': '20px 0 56px rgba(1, 8, 4, 0.24)',
 '--zds-sidebar-tooltip-shadow': '0 14px 36px rgba(1, 8, 4, 0.30)',
 '--zds-topbar-height': '72px',
 '--zds-topbar-surface': 'rgba(6, 11, 7, 0.94)',
 '--zds-topbar-border': 'var(--zds-color-border)',
 '--zds-topbar-profile-surface': 'var(--zds-color-surface-soft)',
 '--zds-transition-fast': '160ms ease',
 '--zds-transition-base': '220ms ease'}

        declarations = re.findall(
            (
                r"(--zds-[A-Za-z0-9_-]+)"
                r"\s*:\s*"
                r"([^;{}]+);"
            ),
            token_block,
        )

        actual_tokens = {
            name: " ".join(
                value.split()
            )
            for name, value in declarations
        }

        self.assertEqual(
            actual_tokens,
            expected_tokens,
        )

        self.assertEqual(
            len(actual_tokens),
            72,
        )

        for token_name in expected_tokens:
            with self.subTest(
                token_name=token_name
            ):
                self.assertEqual(
                    token_block.count(
                        token_name + ":"
                    ),
                    1,
                )

        forbidden_tokens = (
            "!important",
            ":has(",
            "nth-child(",
            "@media",
            "body",
            ".btn",
            ".card",
            ".table",
        )

        for token in forbidden_tokens:
            with self.subTest(
                forbidden_token=token
            ):
                self.assertNotIn(
                    token,
                    token_block,
                )

        root_match = re.search(
            (
                r":root\s*\{"
                r"(.*?)"
                r"\}\s*"
                r"/\* Independent light composition"
            ),
            variables,
            flags=re.DOTALL,
        )

        self.assertIsNotNone(
            root_match,
        )

        root_block = root_match.group(1)

        root_zds_declarations = re.findall(
            (
                r"(--zds-[A-Za-z0-9_-]+)"
                r"\s*:\s*"
                r"([^;{}]+);"
            ),
            root_block,
        )

        root_zds_tokens = {
            name: " ".join(
                value.split()
            )
            for name, value in root_zds_declarations
        }

        self.assertEqual(
            root_zds_tokens,
            expected_tokens,
        )

        expected_brand_tokens = {'--zarya-forest-950': '#041008',
 '--zarya-forest-900': '#07180e',
 '--zarya-forest-800': '#0b2817',
 '--zarya-forest-700': '#087a36',
 '--zarya-growth-500': '#78c442',
 '--zarya-dawn-500': '#e3b341',
 '--zarya-dawn-300': '#f0d27a',
 '--zarya-linen-100': '#f6f1e6',
 '--zarya-linen-50': '#fbf8f0',
 '--zarya-graphite-900': '#1e2d24',
 '--zarya-graphite-700': '#42564a'}

        brand_declarations = re.findall(
            (
                r"(--zarya-[A-Za-z0-9_-]+)"
                r"\s*:\s*"
                r"([^;{}]+);"
            ),
            root_block,
        )

        actual_brand_tokens = {
            name: " ".join(
                value.split()
            )
            for name, value in brand_declarations
        }

        self.assertEqual(
            actual_brand_tokens,
            expected_brand_tokens,
        )

        self.assertIn(
            "body.light-theme {",
            variables,
        )
        self.assertIn(
            (
                "--zds-color-canvas: "
                "var(--zarya-linen-100);"
            ),
            variables,
        )
        self.assertIn(
            (
                "--zds-sidebar-active-accent: "
                "#a86f00;"
            ),
            variables,
        )

        self.assertEqual(
            app_css.count(
                (
                    '@import url('
                    '"./base/variables.css"'
                    ");"
                )
            ),
            1,
        )

        variables_import_position = (
            app_css.index(
                "./base/variables.css"
            )
        )

        reset_import_position = (
            app_css.index(
                "./base/reset.css"
            )
        )

        typography_import_position = (
            app_css.index(
                "./base/typography.css"
            )
        )

        self.assertLess(
            variables_import_position,
            reset_import_position,
        )

        self.assertLess(
            reset_import_position,
            typography_import_position,
        )

        legacy_tokens = (
            "--color-bg-main:",
            "--color-primary:",
            "--radius-md:",
            "--z-bg:",
            "--z-surface:",
            "--z-text:",
            "--z-accent:",
        )

        for legacy_token in legacy_tokens:
            with self.subTest(
                legacy_token=legacy_token
            ):
                self.assertEqual(
                    root_block.count(
                        legacy_token
                    ),
                    1,
                )
