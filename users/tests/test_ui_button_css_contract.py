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
    def test_partial_upload_status_is_not_duplicated_in_payment_feature(
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

        payment_feature_css = (
            base_dir
            / "static"
            / "css"
            / "features"
            / "partial-payments.css"
        ).read_text(
            encoding="utf-8"
        )

        generic_partial_rule = """\
.status-partial {
    background: rgba(245, 158, 11, .14);
    color: #fbbf24;
    border-color: rgba(245, 158, 11, .25);
}
"""

        self.assertEqual(
            component_css.count(
                generic_partial_rule
            ),
            1,
        )

        self.assertNotIn(
            generic_partial_rule,
            payment_feature_css,
        )

        self.assertIn(
            ".status-badge.status-partially_paid {",
            payment_feature_css,
        )

        self.assertIn(
            (
                ".payment-mini-partial "
                ".payment-mini-status {"
            ),
            payment_feature_css,
        )
    def test_partially_paid_registry_status_is_owned_by_payment_feature(
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

        payment_feature_css = (
            base_dir
            / "static"
            / "css"
            / "features"
            / "partial-payments.css"
        ).read_text(
            encoding="utf-8"
        )

        partially_paid_rule = """\
.status-badge.status-partially_paid {
    background: rgba(168, 85, 247, 0.16) !important;
    color: #e9d5ff !important;
    border: 1px solid rgba(192, 132, 252, 0.30) !important;
}
"""

        self.assertNotIn(
            partially_paid_rule,
            component_css,
        )

        self.assertEqual(
            payment_feature_css.count(
                partially_paid_rule
            ),
            1,
        )

        self.assertIn(
            (
                ".payment-mini-partial "
                ".payment-mini-status {"
            ),
            payment_feature_css,
        )
    def test_partial_payment_mini_status_is_owned_by_payment_feature(
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

        payment_feature_css = (
            base_dir
            / "static"
            / "css"
            / "features"
            / "partial-payments.css"
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

        partial_mini_rule = """\
.payment-mini-partial .payment-mini-status {
    color: #fde68a;
    background: rgba(202, 138, 4, 0.20);
}
"""

        self.assertNotIn(
            partial_mini_rule,
            component_css,
        )

        self.assertEqual(
            payment_feature_css.count(
                partial_mini_rule
            ),
            1,
        )

        self.assertLess(
            app_css.index(
                "./components/badges.css"
            ),
            app_css.index(
                "./features/partial-payments.css"
            ),
        )
