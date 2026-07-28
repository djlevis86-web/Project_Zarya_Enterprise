from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


class DashboardPageHeaderSemanticScopeV1Tests(
    SimpleTestCase
):
    repo_root = Path(
        __file__
    ).resolve().parents[2]

    template_path = (
        repo_root
        / "templates"
        / "dashboard.html"
    )

    css_root = (
        repo_root
        / "static"
        / "css"
    )

    def test_dashboard_page_header_semantic_scope_v1_contract(
        self,
    ) -> None:
        template_text = (
            self.template_path.read_text(
                encoding="utf-8-sig",
            )
            .replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
        )

        hero_matches = re.findall(
            (
                r'<section\s+'
                r'class="dashboard-hero '
                r'dashboard-page-header-v1"'
                r'[\s\S]*?</section>'
            ),
            template_text,
        )

        self.assertEqual(
            len(hero_matches),
            1,
        )

        hero_text = hero_matches[0]

        class_values = [
            set(
                value.split()
            )
            for value in re.findall(
                r'class="([^"]+)"',
                hero_text,
            )
        ]

        required_tokens = {
            "dashboard-page-header-v1",
            "dashboard-page-header-copy-v1",
            "dashboard-page-header-kicker-v1",
            "dashboard-page-title-v1",
            "dashboard-page-subtitle-v1",
            "dashboard-page-header-actions-v1",
            "dashboard-page-header-summary-v1",
        }

        for token in sorted(
            required_tokens
        ):
            self.assertEqual(
                template_text.count(
                    token
                ),
                1,
            )

            self.assertTrue(
                any(
                    token in class_value
                    for class_value in class_values
                ),
                msg=(
                    "Semantic token is not in "
                    "a class attribute: "
                    + token
                ),
            )

        required_pairs = (
            (
                "dashboard-hero",
                "dashboard-page-header-v1",
            ),
            (
                "dashboard-hero-main",
                "dashboard-page-header-copy-v1",
            ),
            (
                "dashboard-kicker",
                "dashboard-page-header-kicker-v1",
            ),
            (
                "dashboard-title",
                "dashboard-page-title-v1",
            ),
            (
                "dashboard-hero-actions",
                "dashboard-page-header-actions-v1",
            ),
            (
                "dashboard-hero-side",
                "dashboard-page-header-summary-v1",
            ),
        )

        for legacy_token, semantic_token in (
            required_pairs
        ):
            self.assertTrue(
                any(
                    {
                        legacy_token,
                        semantic_token,
                    }.issubset(
                        class_value
                    )
                    for class_value in class_values
                ),
                msg=(
                    legacy_token
                    + " and "
                    + semantic_token
                    + " must remain on the "
                    "same element."
                ),
            )

        self.assertIn(
            (
                '<p class="'
                'dashboard-page-subtitle-v1">'
            ),
            template_text,
        )

        self.assertIn(
            'aria-labelledby="dashboard-title"',
            template_text,
        )

        self.assertIn(
            'id="dashboard-title"',
            template_text,
        )

        for url_name in (
            "upload_invoice",
            "invoice_list",
            "payment_registry",
        ):
            self.assertEqual(
                hero_text.count(
                    (
                        "{% url '"
                        + url_name
                        + "' %}"
                    )
                ),
                1,
            )

        for variable in (
            "{{ total_count }}",
            "{{ month_count }}",
        ):
            self.assertEqual(
                hero_text.count(
                    variable
                ),
                1,
            )

        template_tokens = set().union(
            *class_values
        )

        shared_visual_tokens = {
            "page-header-v1",
            "page-header-copy-v1",
            "page-header-actions-v1",
            "page-title",
            "page-subtitle",
        }

        self.assertTrue(
            shared_visual_tokens.isdisjoint(
                template_tokens
            )
        )

        visual_relative_path = (
            "static/css/features/"
            "dashboard-page-header-visual-v1.css"
        )

        visual_path = (
            self.repo_root
            / visual_relative_path
        )

        self.assertTrue(
            visual_path.is_file()
        )

        for token in sorted(
            required_tokens
        ):
            selector_files = []

            for css_path in self.css_root.rglob(
                "*.css"
            ):
                css_text = css_path.read_text(
                    encoding="utf-8-sig",
                    errors="replace",
                )

                if (
                    "."
                    + token
                ) in css_text:
                    selector_files.append(
                        css_path.relative_to(
                            self.repo_root
                        ).as_posix()
                    )

            self.assertEqual(
                selector_files,
                [
                    visual_relative_path
                ],
                msg=(
                    "Dashboard semantic selector "
                    "ownership mismatch: "
                    + token
                ),
            )
