from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PageHeaderSemanticScopeV1Tests(
    SimpleTestCase
):
    expected_template_files = (
        "templates/dashboard.html",

        "templates/invoices/"
        "counterparties_missing_requisites.html",

        "templates/invoices/"
        "counterparty_detail.html",

        "templates/invoices/"
        "counterparty_directory.html",

        "templates/invoices/"
        "counterparty_form.html",

        "templates/invoices/detail.html",

        "templates/invoices/edit_invoice.html",

        "templates/invoices/"
        "import_counterparties_1c.html",

        "templates/invoices/"
        "invoice_assign_counterparty.html",

        "templates/invoices/invoice_list.html",

        "templates/invoices/ocr_queue.html",

        "templates/invoices/payment_registry.html",

        "templates/invoices/"
        "payment_registry_detail.html",

        "templates/invoices/payment_schedule.html",

        "templates/invoices/"
        "unmatched_counterparties.html",

        "templates/invoices/"
        "upload_batch_detail.html",

        "templates/invoices/upload_batches.html",

        "templates/invoices/upload_invoice.html",

        "templates/invoices/upload_result.html",

        "templates/profile.html",

        "templates/users/user_admin_form.html",

        "templates/users/user_admin_list.html",
    )

    no_action_files = frozenset(
        {
            "templates/invoices/edit_invoice.html",
            "templates/profile.html",
        }
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

    def test_page_header_semantic_scope_v1_contract(
        self,
    ):
        expected_files = frozenset(
            self.expected_template_files
        )

        semantic_files: set[str] = set()

        total_outer = 0
        total_copy = 0
        total_actions = 0
        total_title = 0
        total_subtitle = 0

        for relative_path in (
            self.expected_template_files
        ):
            template_path = (
                Path(settings.BASE_DIR)
                / relative_path
            )

            self.assertTrue(
                template_path.is_file(),
                relative_path,
            )

            text = self.normalize_text(
                template_path
            )

            tokens = self.class_tokens(
                text
            )

            outer_count = tokens.count(
                "page-header-v1"
            )

            copy_count = tokens.count(
                "page-header-copy-v1"
            )

            action_count = tokens.count(
                "page-header-actions-v1"
            )

            title_count = tokens.count(
                "page-title"
            )

            subtitle_count = tokens.count(
                "page-subtitle"
            )

            expected_action_count = (
                0
                if relative_path
                in self.no_action_files
                else 1
            )

            with self.subTest(
                relative_path=relative_path,
                token="page-header-v1",
            ):
                self.assertEqual(
                    outer_count,
                    1,
                )

            with self.subTest(
                relative_path=relative_path,
                token="page-header-copy-v1",
            ):
                self.assertEqual(
                    copy_count,
                    1,
                )

            with self.subTest(
                relative_path=relative_path,
                token="page-header-actions-v1",
            ):
                self.assertEqual(
                    action_count,
                    expected_action_count,
                )

            with self.subTest(
                relative_path=relative_path,
                token="page-title",
            ):
                self.assertEqual(
                    title_count,
                    1,
                )

            with self.subTest(
                relative_path=relative_path,
                token="page-subtitle",
            ):
                self.assertEqual(
                    subtitle_count,
                    1,
                )

            self.assertEqual(
                tokens.count(
                    "page-header"
                ),
                1,
            )

            total_outer += outer_count
            total_copy += copy_count
            total_actions += action_count
            total_title += title_count
            total_subtitle += subtitle_count

        templates_root = (
            Path(settings.BASE_DIR)
            / "templates"
        )

        for template_path in (
            templates_root.rglob(
                "*.html"
            )
        ):
            text = self.normalize_text(
                template_path
            )

            tokens = self.class_tokens(
                text
            )

            if any(
                token in tokens
                for token in (
                    "page-header-v1",
                    "page-header-copy-v1",
                    "page-header-actions-v1",
                )
            ):
                semantic_files.add(
                    template_path.relative_to(
                        settings.BASE_DIR
                    ).as_posix()
                )

        self.assertEqual(
            frozenset(
                semantic_files
            ),
            expected_files,
        )

        self.assertEqual(
            total_outer,
            22,
        )

        self.assertEqual(
            total_copy,
            22,
        )

        self.assertEqual(
            total_actions,
            20,
        )

        self.assertEqual(
            total_title,
            22,
        )

        self.assertEqual(
            total_subtitle,
            22,
        )
