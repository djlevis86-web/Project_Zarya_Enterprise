from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InvoiceDetailSemanticScopeV1Tests(
    SimpleTestCase
):
    template_relative_path = (
        "templates/invoices/detail.html"
    )

    class_attribute_pattern = re.compile(
        (
            r"\bclass\s*=\s*"
            r"(?P<quote>[\"'])"
            r"(?P<value>.*?)"
            r"(?P=quote)"
        ),
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    expected_url_names = frozenset(
        {
            "add_comment",
            "add_invoice_payment",
            "cancel_invoice_payment",
            "counterparty_detail",
            "delete_invoice",
            "edit_invoice",
            "enqueue_ocr_jobs",
            "invoice_assign_counterparty",
            "invoice_list",
            "repeat_ocr",
        }
    )

    expected_single_tokens = (
        "invoice-detail-page-v1",
        "invoice-detail-header-v1",
        "invoice-detail-header-copy-v1",
        "invoice-detail-title-v1",
        "invoice-detail-subtitle-v1",
        "invoice-detail-actions-v1",
        "invoice-detail-workspace-v1",
        "invoice-detail-primary-v1",
        "invoice-detail-preview-v1",
        "invoice-detail-overview-v1",
        "invoice-detail-counterparty-v1",
        "invoice-detail-payment-v1",
        "invoice-detail-payments-v1",
        "invoice-detail-explainable-ocr-v1",
        "invoice-detail-history-v1",
        "invoice-detail-comments-v1",
        "invoice-detail-document-v1",
        "invoice-detail-ocr-facts-v1",
    )

    expected_section_ids = (
        "invoice-detail-overview-title-v1",
        "invoice-detail-counterparty-title-v1",
        "invoice-detail-payment-title-v1",
        "invoice-detail-payments-title-v1",
        "invoice-detail-ocr-title-v1",
        "invoice-detail-history-title-v1",
        "invoice-detail-comments-title-v1",
        "invoice-detail-document-title-v1",
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.template_path = (
            Path(settings.BASE_DIR)
            / cls.template_relative_path
        )

        cls.text = cls.template_path.read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        cls.tokens = cls.class_tokens(
            cls.text
        )

    @classmethod
    def class_tokens(
        cls,
        text: str,
    ) -> tuple[str, ...]:
        tokens: list[str] = []

        for match in (
            cls.class_attribute_pattern.finditer(
                text
            )
        ):
            tokens.extend(
                token
                for token in re.split(
                    r"\s+",
                    match.group(
                        "value"
                    ).strip(),
                )
                if token
            )

        return tuple(tokens)

    def test_invoice_detail_semantic_scope_v1_contract(
        self,
    ):
        self.assertTrue(
            self.template_path.is_file()
        )

        for token in (
            self.expected_single_tokens
        ):
            with self.subTest(
                token=token
            ):
                self.assertEqual(
                    self.tokens.count(token),
                    1,
                )

        self.assertEqual(
            self.tokens.count(
                "invoice-detail-ocr-fact-v1"
            ),
            4,
        )

        self.assertEqual(
            self.tokens.count(
                "invoice-detail-ocr-decision-v1"
            ),
            3,
        )

        self.assertEqual(
            len(
                re.findall(
                    (
                        r"<main\b[^>]*"
                        r"\binvoice-detail-workspace-v1\b"
                    ),
                    self.text,
                    flags=(
                        re.IGNORECASE
                        | re.DOTALL
                    ),
                )
            ),
            1,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"</main>",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            1,
        )

        for section_id in (
            self.expected_section_ids
        ):
            with self.subTest(
                section_id=section_id
            ):
                self.assertEqual(
                    self.text.count(
                        'id="'
                        + section_id
                        + '"'
                    ),
                    1,
                )

                self.assertEqual(
                    self.text.count(
                        'aria-labelledby="'
                        + section_id
                        + '"'
                    ),
                    1,
                )

        self.assertEqual(
            self.text.count(
                'role="toolbar"'
            ),
            1,
        )

        self.assertEqual(
            self.text.count(
                (
                    'aria-label="Действия '
                    'с документом"'
                )
            ),
            1,
        )

    def test_invoice_detail_existing_behavior_contract_is_preserved(
        self,
    ):
        url_names = frozenset(
            re.findall(
                (
                    r"\{%\s*url\s+"
                    r"['\"]([^'\"]+)['\"]"
                ),
                self.text,
            )
        )

        self.assertEqual(
            url_names,
            self.expected_url_names,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<form\b",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            6,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<button\b",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            8,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<a\b",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            6,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"\bonsubmit\s*=",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            3,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"\bonclick\s*=",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            1,
        )

        self.assertEqual(
            len(
                re.findall(
                    r"<script\b",
                    self.text,
                    flags=re.IGNORECASE,
                )
            ),
            1,
        )

        self.assertNotRegex(
            self.text,
            r"\bstyle\s*=",
        )

        self.assertIn(
            "pdfjs/pdf.mjs",
            self.text,
        )

        self.assertIn(
            "pdfjs/pdf.worker.mjs",
            self.text,
        )

        for token in (
            "page-header",
            "page-header-v1",
            "page-header-copy-v1",
            "page-header-actions-v1",
            "page-title",
            "page-subtitle",
            "invoice-detail-layout",
            "invoice-detail-left",
            "invoice-detail-right",
        ):
            with self.subTest(
                preserved_token=token
            ):
                self.assertEqual(
                    self.tokens.count(token),
                    1,
                )
