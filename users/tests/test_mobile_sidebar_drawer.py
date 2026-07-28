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
            'data-sidebar-version="v3"',
            'id="sidebar-mobile-toggle"',
            'aria-controls="app-sidebar"',
            'aria-expanded="false"',
            'data-sidebar-close',
            'class="sidebar-mobile-backdrop"',
            'js/sidebar-mobile-drawer.js',
            'js/sidebar-tooltip-v3.js',
            'class="sidebar-icon-sprite-v3"',
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

        self.assertEqual(
            response_html.count(
                'class="nav-icon"'
            ),
            12,
        )

    def test_mobile_sidebar_css_defines_production_drawer(self):
        css_path = (
            Path(
                settings.BASE_DIR
            )
            / "static"
            / "css"
            / "features"
            / "sidebar-visual-v3.css"
        )

        self.assertTrue(
            css_path.exists(),
            msg=(
                "Missing Sidebar V3 stylesheet: "
                f"{css_path}"
            ),
        )

        css_text = css_path.read_text(
            encoding="utf-8"
        )

        required_markers = (
            "@media (max-width: 980px)",
            "body.sidebar-mobile-open",
            "var(--zds-sidebar-drawer-width)",
            "calc(100vw - 48px)",
            ".sidebar-mobile-close",
            ".sidebar-mobile-toggle",
            ".sidebar-mobile-backdrop",
            ".sidebar-account-card",
            "grid-template-columns:",
            "minmax(0, 1fr)",
            "@media (max-width: 520px)",
            "@media (prefers-reduced-motion: reduce)",
        )

        for marker in required_markers:
            with self.subTest(
                marker=marker
            ):
                self.assertIn(
                    marker,
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

    def test_mobile_topbar_keeps_single_row_contract(self):
        repo_root = Path(
            settings.BASE_DIR
        )

        topbar_path = (
            repo_root
            / "static"
            / "css"
            / "layout"
            / "topbar.css"
        )

        topbar_text = topbar_path.read_text(
            encoding="utf-8-sig"
        )

        required_markers = (
            "TOPBAR-PRODUCTION-OWNER-V1-START",
            "@media (max-width: 980px)",
            "height: 68px;",
            "grid-template-columns:",
            "minmax(0, 1fr)",
            "grid-column: 2;",
            "grid-column: 3;",
        )

        for marker in required_markers:
            with self.subTest(
                marker=marker
            ):
                self.assertIn(
                    marker,
                    topbar_text,
                )

        legacy_owner_paths = (
            (
                repo_root
                / "static"
                / "css"
                / "components"
                / "filters.css"
            ),
            (
                repo_root
                / "static"
                / "css"
                / "features"
                / "ocr.css"
            ),
            (
                repo_root
                / "static"
                / "css"
                / "pages"
                / "payment-registry.css"
            ),
        )

        for legacy_path in legacy_owner_paths:
            with self.subTest(
                path=str(legacy_path)
            ):
                legacy_text = legacy_path.read_text(
                    encoding="utf-8-sig"
                )

                self.assertNotRegex(
                    legacy_text,
                    r"(?m)^\s*\.topbar\s*\{",
                    msg=(
                        "Legacy CSS modules must not own "
                        "global .topbar geometry."
                    ),
                )
