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
