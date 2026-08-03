from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DashboardApprovedMockupParityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = Path(settings.BASE_DIR)
        cls.template = (
            cls.base / "templates/dashboard.html"
        ).read_text(encoding="utf-8-sig")
        cls.css = (
            cls.base / "static/css/pages/dashboard.css"
        ).read_text(encoding="utf-8-sig")

    def test_dashboard_uses_compact_work_center_identity(self):
        for token in (
            "dashboard-command-bar",
            "dashboard_greeting_name",
            "request.user.first_name",
            "Добрый день,",
            "Вот что требует внимания сегодня в ОАО «Заря».",
            "Сегодня ·",
            "Загрузить документы",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.template)

        self.assertNotIn("dashboard-command-kicker", self.template)
        self.assertNotIn("request.user.get_full_name", self.template)
        self.assertNotIn("enterprise-dashboard-hero", self.template)
        self.assertNotIn("page-header-v1", self.template)

    def test_dashboard_kpis_show_money_and_document_counts(self):
        for token in (
            "Требует проверки",
            "К оплате сегодня",
            "Просрочено",
            "Готово к реестру",
            "enterprise_dashboard.metrics.0.amount|money_ru",
            "enterprise_dashboard.metrics.1.amount|money_ru",
            "enterprise_dashboard.metrics.2.amount|money_ru",
            "enterprise_dashboard.metrics.3.amount|money_ru",
            "enterprise_dashboard.metrics.0.count",
            "enterprise_dashboard.metrics.3.count",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.template)

    def test_primary_workspace_pairs_tasks_and_payment_chart(self):
        primary = self.template.index(
            'class="dashboard-primary-grid"'
        )
        tasks = self.template.index("Мои задачи")
        chart = self.template.index("График платежей")
        secondary = self.template.index(
            'class="dashboard-secondary-grid"'
        )

        self.assertLess(primary, tasks)
        self.assertLess(tasks, chart)
        self.assertLess(chart, secondary)
        self.assertIn('slice:":4"', self.template)
        self.assertIn("dashboard-chart-empty", self.template)

    def test_dashboard_removes_duplicate_full_width_widget_stack(self):
        for retired in (
            "enterprise-attention-panel",
            "enterprise-dashboard-analytics",
            "enterprise-dashboard-work",
            "enterprise-dashboard-lower",
            "enterprise-chart-donut",
            "dashboard-work-list",
            "Недавние документы",
            "Крупнейшие платежи недели",
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, self.template)

        self.assertEqual(
            self.template.count('class="dashboard-panel '),
            4,
        )

    def test_dashboard_css_enforces_compact_geometry(self):
        for token in (
            "min-height: 78px;",
            "min-height: 84px;",
            "min-height: 132px;",
            "grid-template-columns: minmax(0, 1.16fr) minmax(340px, 0.84fr);",
            "min-height: 66px;",
            "grid-template-columns: repeat(2, minmax(0, 1fr));",
            "@media (max-width: 900px)",
            "grid-template-columns: minmax(0, 1fr) auto;",
            "font-size: clamp(16px, 4.45vw, 18px);",
            "white-space: nowrap;",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.css)

        self.assertNotIn("min-height: 106px", self.css)
        self.assertNotIn("min-height: 120px", self.css)

    def test_responsive_density_contract_avoids_premature_stack_and_wrapped_money(self):
        self.assertNotIn("@media (max-width: 980px)", self.css)
        self.assertIn("@media (max-width: 900px)", self.css)
        self.assertIn("@media (max-width: 360px)", self.css)
        self.assertIn("min-height: 118px;", self.css)
        self.assertIn("max-height: 132px;", self.css)
        self.assertIn("letter-spacing: -0.02em;", self.css)

    def test_chart_legend_wraps_and_primary_panels_balance(self):
        for token in (
            "align-items: stretch;",
            "grid-template-rows: auto minmax(200px, 1fr) auto;",
            "height: 100%;",
            "max-height: none;",
            "flex-wrap: wrap;",
            "overflow-x: visible;",
            "flex: 0 0 100%;",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.css)

        self.assertNotIn("overflow-x: auto;", self.css)

    def test_dashboard_css_has_no_patch_techniques(self):
        self.assertNotIn("!important", self.css)
        self.assertNotIn("nth-child(", self.css)
        self.assertNotIn("rgba(", self.css.lower())
        self.assertNotIn("overflow-x: hidden", self.css)

    def test_mobile_keeps_compact_kpis_and_task_first_order(self):
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn(
            "grid-template-columns: repeat(2, minmax(0, 1fr));",
            self.css,
        )
        self.assertLess(
            self.template.index("Мои задачи"),
            self.template.index("Ближайшие платежи"),
        )
