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

    def test_dashboard_uses_approved_work_center_identity(self):
        for token in (
            "Рабочий центр",
            "Документы и платежи",
            "Всё, что требует решения сегодня, в одном рабочем маршруте.",
            "Загрузить документы",
            "Все документы",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.template)

    def test_dashboard_kpis_match_approved_first_viewport(self):
        for token in (
            "Требует проверки",
            "К оплате сегодня",
            "Просрочено",
            "Оплачено за месяц",
            "Есть блокирующие данные",
            "Закрытые обязательства",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.template)

        self.assertNotIn(
            "enterprise_dashboard.metrics",
            self.template,
        )

    def test_attention_queue_precedes_analytics_and_secondary_work(self):
        attention = self.template.index(
            'class="production-panel enterprise-attention-panel"'
        )
        analytics = self.template.index(
            'class="enterprise-dashboard-analytics"'
        )
        work = self.template.index(
            'class="enterprise-dashboard-work"'
        )
        lower = self.template.index(
            'class="enterprise-dashboard-lower"'
        )

        self.assertLess(attention, analytics)
        self.assertLess(analytics, work)
        self.assertLess(work, lower)

    def test_attention_queue_keeps_business_columns(self):
        for token in (
            "dashboard-work-identity",
            "dashboard-work-reason",
            "dashboard-work-date",
            "dashboard-work-action",
            "Открыть очередь",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.template)

    def test_dashboard_css_has_no_patch_techniques(self):
        self.assertNotIn("!important", self.css)
        self.assertNotIn("nth-child(", self.css)
        self.assertNotIn("rgba(", self.css.lower())

    def test_mobile_attention_queue_remains_before_analytics(self):
        self.assertIn(
            "@media (max-width: 760px)",
            self.css,
        )
        self.assertIn(
            ".dashboard-work-reason,\n    .dashboard-work-date,\n    .dashboard-work-action",
            self.css,
        )
        self.assertIn(
            "grid-column: 2;",
            self.css,
        )
