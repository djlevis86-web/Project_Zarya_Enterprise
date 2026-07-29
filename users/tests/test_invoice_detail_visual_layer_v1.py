from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InvoiceDetailVisualLayerV1Tests(
    SimpleTestCase
):
    css_relative_path = (
        "static/css/pages/invoice-detail.css"
    )
    template_relative_path = (
        "templates/invoices/detail.html"
    )
    app_css_relative_path = (
        "static/css/app.css"
    )

    required_selectors = (
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-workspace-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-actions-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-primary-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-preview-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-ocr-facts-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-ocr-fact-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".invoice-detail-ocr-decision-v1"
        ),
        (
            ".invoice-detail-page-v1 "
            ".payment-left-form"
        ),
        (
            ".invoice-detail-page-v1 "
            ".pdf-toolbar"
        ),
        (
            ".invoice-detail-page-v1 "
            "#pdf-container"
        ),
        (
            ".invoice-detail-page-v1 "
            ".preview-image"
        ),
    )

    required_tokens = (
        "--zds-color-surface-elevated",
        "--zds-color-surface-soft",
        "--zds-color-control",
        "--zds-color-text",
        "--zds-color-text-muted",
        "--zds-color-border",
        "--zds-color-border-brand",
        "--zds-color-border-dawn",
        "--zds-color-accent-strong",
        "--zds-color-dawn",
        "--zds-color-success",
        "--zds-color-warning",
        "--zds-color-danger",
        "--zds-radius-card",
        "--zds-shadow-card",
        "--zds-shadow-focus",
    )

    @staticmethod
    def read(
        relative_path: str,
    ) -> str:
        return (
            Path(settings.BASE_DIR)
            / relative_path
        ).read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

    def test_visual_layer_is_single_page_scoped_owner(
        self,
    ):
        css = self.read(
            self.css_relative_path
        )

        self.assertEqual(
            css.count(
                "INVOICE-DETAIL-VISUAL-LAYER-V1-START"
            ),
            1,
        )
        self.assertEqual(
            css.count(
                "INVOICE-DETAIL-VISUAL-LAYER-V1-END"
            ),
            1,
        )

        for selector in (
            self.required_selectors
        ):
            with self.subTest(
                selector=selector
            ):
                self.assertIn(
                    selector,
                    css,
                )

        for token in self.required_tokens:
            with self.subTest(
                token=token
            ):
                self.assertIn(
                    token,
                    css,
                )

        self.assertNotIn(
            "!important",
            css,
        )

        self.assertNotRegex(
            css,
            r"#[0-9a-fA-F]{3,8}\b",
        )

        self.assertNotIn(
            "LEGACY-MIGRATION",
            css,
        )

        self.assertNotIn(
            "Стили скопированы из legacy",
            css,
        )

    def test_visual_layer_has_responsive_and_accessibility_contract(
        self,
    ):
        css = self.read(
            self.css_relative_path
        )

        for media_contract in (
            "@media (max-width: 1280px)",
            "@media (max-width: 900px)",
            "@media (max-width: 640px)",
            (
                "@media "
                "(prefers-reduced-motion: reduce)"
            ),
        ):
            with self.subTest(
                media_contract=media_contract
            ):
                self.assertEqual(
                    css.count(
                        media_contract
                    ),
                    1,
                )

        self.assertIn(
            ":focus-visible",
            css,
        )
        self.assertIn(
            "scroll-margin-top",
            css,
        )
        self.assertIn(
            "overscroll-behavior: contain",
            css,
        )
        self.assertIn(
            "min-height: "
            "var(--zds-control-height-default)",
            css,
        )

        open_braces = css.count("{")
        close_braces = css.count("}")

        self.assertEqual(
            open_braces,
            close_braces,
        )
        self.assertGreater(
            open_braces,
            40,
        )

    def test_template_and_import_contract_are_preserved(
        self,
    ):
        template = self.read(
            self.template_relative_path
        )
        app_css = self.read(
            self.app_css_relative_path
        )

        for token in (
            "invoice-detail-page-v1",
            "invoice-detail-header-v1",
            "invoice-detail-actions-v1",
            "invoice-detail-workspace-v1",
            "invoice-detail-primary-v1",
            "invoice-detail-preview-v1",
            "invoice-detail-payments-v1",
            "invoice-detail-explainable-ocr-v1",
            "invoice-detail-document-v1",
        ):
            with self.subTest(
                template_token=token
            ):
                self.assertIn(
                    token,
                    template,
                )

        self.assertEqual(
            app_css.count(
                (
                    '@import url('
                    '"./pages/invoice-detail.css"'
                    ');'
                )
            ),
            1,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"\bstyle\s*=",
                    template,
                    flags=re.IGNORECASE,
                )
            ),
            0,
        )

        self.assertIn(
            "pdfjs/pdf.mjs",
            template,
        )
        self.assertIn(
            "pdfjs/pdf.worker.mjs",
            template,
        )
