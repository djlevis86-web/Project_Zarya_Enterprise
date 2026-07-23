from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DashboardProcessGridTests(SimpleTestCase):
    def test_workflow_steps_use_two_column_grid_on_wide_desktop(self):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "dashboard.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        )

        expected_rule = """\
@media (min-width: 1281px) {
    .dashboard-grid-two > .card:has(
        .dashboard-workflow-title-v1
    ) .process-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        align-items: stretch;
    }
}
"""

        self.assertIn(
            expected_rule,
            css,
        )

    def test_bot_report_has_spacing_before_dashboard_workflow_grid(self):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "dashboard.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        )

        expected_rule = """\
.dashboard-bot-report-v2 + .dashboard-grid-two {
    margin-top: 22px;
}
"""

        self.assertIn(
            expected_rule,
            css,
        )

    def test_dashboard_work_blocks_use_semantic_page_scoped_layout(
        self,
    ):
        template_path = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dashboard.html"
        )

        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "pages"
            / "dashboard.css"
        )

        template = template_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        css = css_path.read_text(
            encoding="utf-8"
        ).replace(
            "\r\n",
            "\n",
        )

        self.assertEqual(
            template.count(
                "dashboard-work-blocks-v1"
            ),
            1,
        )

        self.assertEqual(
            template.count(
                "dashboard-work-panel-v1"
            ),
            2,
        )

        self.assertEqual(
            template.count(
                "dashboard-quick-actions-panel-v1"
            ),
            1,
        )

        self.assertEqual(
            template.count(
                "dashboard-workflow-panel-v1"
            ),
            1,
        )

        work_start = template.index(
            "dashboard-work-blocks-v1"
        )

        route_tokens = (
            "{% url 'upload_invoice' %}",
            "{% url 'unmatched_counterparties' %}",
            (
                "{% url "
                "'counterparties_missing_requisites' %}"
            ),
            "{% url 'payment_registry' %}",
        )

        route_positions = [
            template.index(
                token,
                work_start,
            )
            for token in route_tokens
        ]

        self.assertEqual(
            route_positions,
            sorted(route_positions),
        )

        start_marker = (
            "/* DASHBOARD-WORK-BLOCKS-UX-"
            "PILOT-V1-START */"
        )

        end_marker = (
            "/* DASHBOARD-WORK-BLOCKS-UX-"
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

        required_tokens = (
            (
                ".dashboard-page "
                ".dashboard-work-blocks-v1 {"
            ),
            (
                ".dashboard-page "
                ".dashboard-work-panel-v1 {"
            ),
            (
                ".dashboard-page "
                ".dashboard-quick-actions-panel-v1"
                "\n.quick-action-grid {"
            ),
            (
                ".dashboard-page "
                ".dashboard-workflow-panel-v1"
                "\n.process-list {"
            ),
            (
                ".dashboard-page "
                ".dashboard-quick-actions-panel-v1"
                "\n.quick-action-card {"
            ),
            (
                ".dashboard-page "
                ".dashboard-workflow-panel-v1"
                "\n.process-item {"
            ),
            "@media (max-width: 1280px) {",
            "@media (max-width: 720px) {",
        )

        for token in required_tokens:
            with self.subTest(
                token=token
            ):
                self.assertIn(
                    token,
                    pilot_css,
                )

        forbidden_tokens = (
            "\n.dashboard-work-blocks-v1 {",
            "\n.dashboard-work-panel-v1 {",
            "\n.dashboard-quick-actions-panel-v1 {",
            "\n.dashboard-workflow-panel-v1 {",
            ":has(",
        )

        for token in forbidden_tokens:
            with self.subTest(
                token=token
            ):
                self.assertNotIn(
                    token,
                    pilot_css,
                )
