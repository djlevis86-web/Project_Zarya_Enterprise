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
