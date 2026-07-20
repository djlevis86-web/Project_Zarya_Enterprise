from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class MobileSidebarDrawerTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="mobile-sidebar-user",
            email="mobile-sidebar-user@example.com",
            password="pass12345",
            is_staff=True,
        )

    def test_authenticated_layout_contains_mobile_sidebar_controls(self):
        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        required_markers = (
            'id="app-sidebar"',
            'id="sidebar-mobile-toggle"',
            'aria-controls="app-sidebar"',
            'aria-expanded="false"',
            'data-sidebar-close',
            'class="sidebar-mobile-backdrop"',
            'js/sidebar-mobile-drawer.js',
        )

        for marker in required_markers:
            with self.subTest(
                marker=marker
            ):
                self.assertContains(
                    response,
                    marker,
                )

        response_html = response.content.decode(
            "utf-8"
        )

        self.assertEqual(
            response_html.count(
                'id="app-sidebar"'
            ),
            1,
        )

        self.assertEqual(
            response_html.count(
                'id="sidebar-mobile-toggle"'
            ),
            1,
        )

        self.assertEqual(
            response_html.count(
                'class="sidebar-mobile-backdrop"'
            ),
            1,
        )

    def test_mobile_sidebar_css_forces_single_column_navigation(self):
        css_path = (
            Path(
                settings.BASE_DIR
            )
            / "static"
            / "css"
            / "features"
            / "sidebar-fixed-left.css"
        )

        self.assertTrue(
            css_path.exists(),
            msg=(
                "Missing sidebar stylesheet: "
                f"{css_path}"
            ),
        )

        css_text = css_path.read_text(
            encoding="utf-8"
        )

        expected_block = """\
/* MOBILE-DRAWER-SINGLE-COLUMN-V1-START */
@media (max-width: 980px) {
    .sidebar .sidebar-nav {
        display: flex !important;
        flex-direction: column !important;
        grid-template-columns: 1fr !important;
        align-items: stretch !important;
        gap: 18px !important;
    }

    .sidebar .sidebar-nav .nav-section {
        width: 100% !important;
        min-width: 0 !important;
    }
}
/* MOBILE-DRAWER-SINGLE-COLUMN-V1-END */
"""

        self.assertIn(
            expected_block,
            css_text,
        )

    def test_mobile_sidebar_script_defines_required_close_paths(self):
        script_path = (
            Path(
                settings.BASE_DIR
            )
            / "static"
            / "js"
            / "sidebar-mobile-drawer.js"
        )

        self.assertTrue(
            script_path.exists(),
            msg=(
                "Missing mobile sidebar script: "
                f"{script_path}"
            ),
        )

        script_text = script_path.read_text(
            encoding="utf-8"
        )

        required_markers = (
            "sidebar-mobile-open",
            "sidebar-mobile-toggle",
            "data-sidebar-close",
            "aria-expanded",
            "Escape",
            "matchMedia",
            "nav-link",
            "focus",
        )

        for marker in required_markers:
            with self.subTest(
                marker=marker
            ):
                self.assertIn(
                    marker,
                    script_text,
                )
