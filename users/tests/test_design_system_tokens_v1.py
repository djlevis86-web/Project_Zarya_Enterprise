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

        expected_tokens = {
            "--zds-font-family-sans": (
                "var(--font-family-base)"
            ),
            "--zds-color-canvas": "#060806",
            "--zds-color-canvas-deep": "#020617",
            "--zds-color-surface": (
                "rgba(15, 23, 42, 0.72)"
            ),
            "--zds-color-surface-soft": (
                "rgba(255, 255, 255, 0.035)"
            ),
            "--zds-color-surface-elevated": (
                "rgba(15, 23, 42, 0.62)"
            ),
            "--zds-color-text": "#f8fafc",
            "--zds-color-text-soft": "#cbd5e1",
            "--zds-color-text-muted": "#94a3b8",
            "--zds-color-border": (
                "rgba(148, 163, 184, 0.18)"
            ),
            "--zds-color-border-strong": (
                "rgba(148, 163, 184, 0.35)"
            ),
            "--zds-color-accent": "#27ae60",
            "--zds-color-accent-strong": "#22c55e",
            "--zds-color-accent-soft": (
                "rgba(39, 174, 96, 0.14)"
            ),
            "--zds-color-success": "#22c55e",
            "--zds-color-warning": "#f59e0b",
            "--zds-color-danger": "#ef4444",
            "--zds-color-info": "#3b82f6",
            "--zds-space-1": "4px",
            "--zds-space-2": "8px",
            "--zds-space-3": "12px",
            "--zds-space-4": "16px",
            "--zds-space-6": "24px",
            "--zds-space-8": "32px",
            "--zds-radius-badge": "8px",
            "--zds-radius-control": "10px",
            "--zds-radius-panel": "12px",
            "--zds-radius-card": "16px",
            "--zds-control-height-compact": "40px",
            "--zds-control-height-default": "42px",
            "--zds-table-row-height-compact": "44px",
            "--zds-table-row-height-default": "48px",
            "--zds-touch-target-min": "40px",
            "--zds-shadow-card": (
                "0 10px 24px rgba(0, 0, 0, 0.14)"
            ),
            "--zds-shadow-focus": (
                "0 0 0 3px rgba(34, 197, 94, 0.14)"
            ),
            "--zds-transition-fast": "160ms ease",
            "--zds-transition-base": "220ms ease",
        }

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
                    variables.count(
                        legacy_token
                    ),
                    1,
                )
