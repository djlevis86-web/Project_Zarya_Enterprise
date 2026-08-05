from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.test import SimpleTestCase


class BrandLayerV1Tests(SimpleTestCase):
    repo_root = Path(__file__).resolve().parents[2]

    base_template = repo_root / "templates" / "base.html"
    login_template = repo_root / "templates" / "login.html"
    dashboard_template = repo_root / "templates" / "dashboard.html"

    variables_css = (
        repo_root
        / "static"
        / "css"
        / "base"
        / "variables.css"
    )

    sidebar_css = (
        repo_root
        / "static"
        / "css"
        / "features"
        / "sidebar-visual-v3.css"
    )

    topbar_css = (
        repo_root
        / "static"
        / "css"
        / "layout"
        / "topbar.css"
    )

    forms_css = (
        repo_root
        / "static"
        / "css"
        / "components"
        / "forms.css"
    )

    dashboard_css = (
        repo_root
        / "static"
        / "css"
        / "pages"
        / "dashboard.css"
    )

    payment_registry_css = (
        repo_root
        / "static"
        / "css"
        / "pages"
        / "payment-registry.css"
    )

    workspace_css = (
        repo_root
        / "static"
        / "css"
        / "components"
        / "documents-payments-workspace.css"
    )

    tables_css = (
        repo_root
        / "static"
        / "css"
        / "components"
        / "tables.css"
    )

    payment_registry_template = (
        repo_root
        / "templates"
        / "invoices"
        / "payment_registry.html"
    )

    payment_registry_detail_template = (
        repo_root
        / "templates"
        / "invoices"
        / "payment_registry_detail.html"
    )

    logo_path = (
        repo_root
        / "static"
        / "images"
        / "brand"
        / "zarya-logo-v1.webp"
    )

    def test_user_facing_branding_is_final(self) -> None:
        paths = (
            self.base_template,
            self.login_template,
            self.dashboard_template,
            (
                self.repo_root
                / "templates"
                / "users"
                / "user_admin_list.html"
            ),
            (
                self.repo_root
                / "templates"
                / "invoices"
                / "counterparty_directory.html"
            ),
            (
                self.repo_root
                / "templates"
                / "invoices"
                / "counterparty_detail.html"
            ),
        )

        combined = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in paths
        )

        self.assertIn("ОАО «Заря»", combined)
        self.assertIn("Документы и платежи", combined)
        self.assertNotIn("Project Zarya Enterprise", combined)
        self.assertNotIn("PROJECT ZARYA ENTERPRISE", combined)

    def test_approved_logo_asset_contract(self) -> None:
        self.assertTrue(self.logo_path.is_file())
        self.assertEqual(
            hashlib.sha256(
                self.logo_path.read_bytes()
            ).hexdigest(),
            "2383072505d0cbe52f730ac22acb180c91a9b4860df886536a68de33eebc3f80",
        )
        self.assertEqual(
            self.logo_path.stat().st_size,
            66542,
        )

    def test_brand_tokens_cover_dark_and_light(self) -> None:
        text = self.variables_css.read_text(
            encoding="utf-8-sig"
        )

        required = (
            "--zarya-forest-700",
            "--zarya-growth-500",
            "--zarya-dawn-500",
            "--zarya-linen-100",
            "--zarya-graphite-900",
            "--zds-color-text-on-accent",
            "--zds-color-control",
            "--zds-color-border-dawn",
            "--zds-sidebar-active-accent",
            "--zds-sidebar-logo-surface",
            "--zds-topbar-height",
            "body.light-theme",
        )

        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_sidebar_uses_approved_brand_asset(self) -> None:
        template = self.base_template.read_text(
            encoding="utf-8-sig"
        )
        css = self.sidebar_css.read_text(
            encoding="utf-8-sig"
        )

        required_template = (
            'data-brand-layer="zarya-digital-horizon-v1"',
            'images/brand/zarya-logo-v1.webp',
            'class="brand-mark-image"',
            'Документы и платежи',
            'aria-current="page"',
        )

        for marker in required_template:
            with self.subTest(marker=marker):
                self.assertIn(marker, template)

        required_css = (
            "Zarya Digital Horizon",
            ".sidebar-brand-area::after",
            ".sidebar .nav-link::after",
            "--zds-sidebar-active-accent",
            "calc(100vw - 48px)",
        )

        for marker in required_css:
            with self.subTest(marker=marker):
                self.assertIn(marker, css)

    def test_topbar_is_compact_and_has_profile_action(self) -> None:
        template = self.base_template.read_text(
            encoding="utf-8-sig"
        )
        css = self.topbar_css.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            'class="topbar-profile-action',
            template,
        )
        self.assertNotIn(
            'class="topbar-subtitle"',
            template,
        )
        self.assertIn("min-height: 68px;", css)
        self.assertIn(".topbar::after", css)

    def test_forms_have_one_semantic_select_owner(self) -> None:
        css = self.forms_css.read_text(
            encoding="utf-8-sig"
        )

        self.assertEqual(
            css.count(
                "FORM-SELECT-COMPONENT-STABLE-V1-START"
            ),
            1,
        )
        self.assertNotIn("0 0 0focus", css)
        self.assertIn(
            "background-color: var(--zds-color-control);",
            css,
        )
        self.assertIn(
            "box-shadow: var(--zds-shadow-focus);",
            css,
        )

    def test_dashboard_compact_surfaces_use_brand_tokens(self) -> None:
        template = self.dashboard_template.read_text(
            encoding="utf-8-sig"
        )
        page_css = self.dashboard_css.read_text(
            encoding="utf-8-sig"
        )

        self.assertEqual(
            template.count('class="dashboard-panel '),
            4,
        )
        self.assertIn(
            "background: var(--zds-color-surface-elevated);",
            page_css,
        )
        self.assertIn(
            "border: 1px solid var(--zds-color-border);",
            page_css,
        )
        self.assertIn(
            ".dashboard-task-row",
            page_css,
        )
        self.assertNotIn(
            "production-panel enterprise-attention-panel",
            template,
        )
        self.assertNotIn(
            "DASHBOARD-ATTENTION-QUEUE-V2",
            page_css,
        )
        self.assertNotIn(
            "DASHBOARD-ATTENTION-UX-PILOT-V1",
            page_css,
        )

    def test_payment_registry_uses_shared_zds_surfaces(self) -> None:
        page_css = self.payment_registry_css.read_text(
            encoding="utf-8-sig"
        )
        workspace_css = self.workspace_css.read_text(
            encoding="utf-8-sig"
        )
        tables_css = self.tables_css.read_text(
            encoding="utf-8-sig"
        )
        registry_template = self.payment_registry_template.read_text(
            encoding="utf-8-sig"
        )
        detail_template = (
            self.payment_registry_detail_template.read_text(
                encoding="utf-8-sig"
            )
        )

        required_page_css = (
            ".registry-active-grid",
            ".registry-readiness-panel",
            ".registry-queue-panel",
            ".registry-current-table",
            ".registry-queue-table",
        )
        for marker in required_page_css:
            with self.subTest(marker=marker):
                self.assertIn(marker, page_css)

        combined_templates = registry_template + detail_template
        required_templates = (
            'data-zds-migrated="payment-registry-v1"',
            'class="zds-table zds-table--dense registry-current-table"',
            'class="zds-table zds-table--dense registry-queue-table"',
            'data-enterprise-screen="payment-registry-detail"',
            "registry-detail-workspace",
        )
        for marker in required_templates:
            with self.subTest(marker=marker):
                self.assertIn(marker, combined_templates)

        for retired_marker in (
            ".enterprise-registry-grid",
            ".enterprise-registry-status-list",
            ".enterprise-registry-queue .enterprise-table",
            "production-panel enterprise-registry-summary",
            "production-panel enterprise-registry-queue",
            "production-panel enterprise-table-panel",
            'class="enterprise-table"',
        ):
            with self.subTest(retired_marker=retired_marker):
                self.assertNotIn(
                    retired_marker,
                    page_css + combined_templates,
                )

        shared_brand_css = workspace_css + tables_css
        for marker in (
            "var(--zds-color-surface-elevated)",
            "var(--zds-color-text)",
            "var(--zds-color-border-brand)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, shared_brand_css)

    def test_topbar_has_one_production_owner(self) -> None:
        owner_text = self.topbar_css.read_text(
            encoding="utf-8-sig"
        )

        self.assertEqual(
            owner_text.count(
                "TOPBAR-PRODUCTION-OWNER-V1-START"
            ),
            1,
        )
        self.assertEqual(
            owner_text.count(
                "TOPBAR-PRODUCTION-OWNER-V1-END"
            ),
            1,
        )
        self.assertIn(
            "@media (max-width: 980px)",
            owner_text,
        )
        self.assertIn(
            "height: 68px;",
            owner_text,
        )
        self.assertIn(
            "grid-column: 1 / 3;",
            owner_text,
        )
        self.assertIn(
            "grid-column: 2;",
            owner_text,
        )
        self.assertIn(
            "grid-column: 3;",
            owner_text,
        )

        topbar_selector = re.compile(
            r"(?m)^\s*\.topbar\s*\{"
        )

        non_owner_matches = []

        css_root = (
            self.repo_root
            / "static"
            / "css"
        )

        for css_path in css_root.rglob("*.css"):
            if css_path == self.topbar_css:
                continue

            css_text = css_path.read_text(
                encoding="utf-8-sig"
            )

            if topbar_selector.search(css_text):
                non_owner_matches.append(
                    css_path.relative_to(
                        self.repo_root
                    ).as_posix()
                )

        self.assertEqual(
            non_owner_matches,
            [],
            msg=(
                "Global .topbar geometry must be owned "
                "only by static/css/layout/topbar.css: "
                + ", ".join(non_owner_matches)
            ),
        )
