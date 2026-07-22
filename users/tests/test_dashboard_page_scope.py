from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DashboardPageScopeTests(SimpleTestCase):
    def test_dashboard_content_uses_single_page_scope_wrapper(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dashboard.html"
        )

        template = template_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        wrapper_token = '<div class="dashboard-page">'

        self.assertEqual(
            template.count(wrapper_token),
            1,
        )

        self.assertIn(
            "{% block content %}\n\n"
            + wrapper_token
            + "\n\n<section",
            template,
        )

        self.assertTrue(
            template.rstrip().endswith(
                "</div>\n\n{% endblock %}"
            )
        )

    def test_dashboard_hero_ux_pilot_is_page_scoped(
        self,
    ):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "dashboard.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        start_marker = (
            "/* DASHBOARD-HERO-UX-"
            "PILOT-V1-START */"
        )

        end_marker = (
            "/* DASHBOARD-HERO-UX-"
            "PILOT-V1-END */"
        )

        self.assertEqual(
            css.count(start_marker),
            1,
        )

        self.assertEqual(
            css.count(end_marker),
            1,
        )

        block_start = css.index(
            start_marker
        )

        block_end = css.index(
            end_marker,
            block_start,
        ) + len(end_marker)

        pilot_css = css[
            block_start:block_end
        ]

        required_selectors = (
            ".dashboard-page .dashboard-hero {",
            ".dashboard-page .dashboard-hero-main {",
            ".dashboard-page .dashboard-title {",
            ".dashboard-page .dashboard-hero-actions {",
            ".dashboard-page .dashboard-hero-side {",
            ".dashboard-page .hero-metric {",
            "@media (max-width: 1280px) {",
            "@media (max-width: 720px) {",
        )

        for selector in required_selectors:
            with self.subTest(
                selector=selector
            ):
                self.assertIn(
                    selector,
                    pilot_css,
                )

        unscoped_selectors = (
            "\n.dashboard-hero {",
            "\n.dashboard-title {",
            "\n.dashboard-hero-actions {",
            "\n.hero-metric {",
        )

        for selector in unscoped_selectors:
            with self.subTest(
                selector=selector
            ):
                self.assertNotIn(
                    selector,
                    pilot_css,
                )
