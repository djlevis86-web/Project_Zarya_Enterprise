from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class UIButtonCssContractTests(SimpleTestCase):
    def test_buttons_component_owns_base_button_font_weight(self):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "components"
            / "buttons.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        )

        base_selector = """\
.btn,
.button,
.action-button,
.primary-btn,
.secondary-btn,
.danger-btn,
.audit-btn {
"""

        selector_start = css.index(base_selector)
        rule_end = css.index("}", selector_start)
        base_rule = css[selector_start:rule_end]

        self.assertIn(
            "font-weight: 850;",
            base_rule,
        )

    def test_badges_component_does_not_override_base_button_font_weight(
        self,
    ):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "components"
            / "badges.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        )

        unexpected_rule = """\
strong,
.sidebar-nav a,
.nav-link,
.nav-item,
.btn,
.status-badge,
.form-group label,
label {
    font-weight: 650;
}
"""

        expected_rule = """\
strong,
.sidebar-nav a,
.nav-link,
.nav-item,
.form-group label,
label {
    font-weight: 650;
}
"""

        self.assertNotIn(
            unexpected_rule,
            css,
        )

        self.assertIn(
            expected_rule,
            css,
        )
    def test_badges_typography_group_does_not_override_status_badge_weight(
        self,
    ):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "components"
            / "badges.css"
        )

        css = css_path.read_text(
            encoding="utf-8"
        )

        unexpected_rule = """\
strong,
.sidebar-nav a,
.nav-link,
.nav-item,
.status-badge,
.form-group label,
label {
    font-weight: 650;
}
"""

        expected_rule = """\
strong,
.sidebar-nav a,
.nav-link,
.nav-item,
.form-group label,
label {
    font-weight: 650;
}
"""

        self.assertNotIn(
            unexpected_rule,
            css,
        )

        self.assertIn(
            expected_rule,
            css,
        )
    def test_payment_schedule_owns_overdue_status_badge_override(
        self,
    ):
        base_dir = Path(settings.BASE_DIR)

        component_css = (
            base_dir
            / "static"
            / "css"
            / "components"
            / "badges.css"
        ).read_text(
            encoding="utf-8"
        )

        page_css = (
            base_dir
            / "static"
            / "css"
            / "pages"
            / "payment-schedule.css"
        ).read_text(
            encoding="utf-8"
        )

        app_css = (
            base_dir
            / "static"
            / "css"
            / "app.css"
        ).read_text(
            encoding="utf-8"
        )

        overdue_rule = """\
.payment-schedule-table .schedule-row-overdue .status-badge.status-rejected {
    background: rgba(239, 68, 68, 0.22) !important;
    color: #fecaca !important;
    border: 1px solid rgba(248, 113, 113, 0.35) !important;
}
"""

        self.assertNotIn(
            overdue_rule,
            component_css,
        )

        self.assertEqual(
            page_css.count(overdue_rule),
            1,
        )

        self.assertLess(
            app_css.index(
                "./components/badges.css"
            ),
            app_css.index(
                "./pages/payment-schedule.css"
            ),
        )
