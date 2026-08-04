from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from invoices.models import Invoice


class InvoiceDetailCompactWorkspaceRenderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="va4-detail-staff",
            email="va4-detail-staff@example.com",
            password="pass12345",
            is_staff=True,
            role=User.Role.MANAGER,
        )
        self.invoice = Invoice.objects.create(
            user=self.user,
            title="VA4 compact workspace",
            file="invoices/va4-compact.pdf",
            original_filename=(
                "very-long-original-invoice-file-name-"
                "for-responsive-layout-validation.pdf"
            ),
            amount=Decimal("125000.00"),
            amount_verified=True,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            invoice_number="VA4-41",
            document_date=date(2026, 8, 4),
            status=Invoice.STATUS_APPROVED,
        )
        self.client.force_login(self.user)

    def test_render_preserves_business_data_and_compact_workspace_order(self):
        response = self.client.get(
            reverse(
                "invoice_detail",
                kwargs={"invoice_id": self.invoice.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        for token in (
            'class="production-panel document-detail-overview"',
            'class="document-detail-primary-grid"',
            "document-data-panel",
            "document-uploaded-by-fact",
            "document-original-panel",
            "document-field-review-panel",
            "document-detail-secondary-grid",
            "document-detail-danger-zone",
            "document-detail-title-row",
            "document-detail-status-badge",
            "field-review-status-static",
            "field-review-row-action",
            "delete-invoice-modal",
            'aria-label="',
        ):
            self.assertIn(token, html)

        self.assertLess(
            html.index("document-data-panel"),
            html.index("document-original-panel"),
        )
        self.assertLess(
            html.index("document-original-panel"),
            html.index("document-field-review-panel"),
        )
        self.assertLess(
            html.index("document-field-review-panel"),
            html.index("document-detail-secondary-grid"),
        )
        self.assertLess(
            html.index("document-detail-secondary-grid"),
            html.index("document-detail-danger-zone"),
        )

        self.assertContains(response, "Система и оригинал")
        self.assertContains(response, "Все документы")
        self.assertContains(response, "Удалить документ…")
        self.assertContains(response, "Подтвердить значение")
        self.assertNotContains(response, "Открыть проверку")
        self.assertNotContains(response, "Подтвердить итоговое значение")
        self.assertNotContains(response, "<span>Опасная зона</span>")
        self.assertNotContains(response, "Документ к оплате")
        self.assertContains(response, "Состояние и история оплат")
        self.assertContains(response, "История и комментарии")
        self.assertContains(response, "Редактировать")
        self.assertContains(response, "Привязать контрагента")
        self.assertNotIn(">i</button>", html)


class InvoiceDetailCompactWorkspaceStaticTests(SimpleTestCase):
    template_relative = "templates/invoices/detail.html"
    css_relative = "static/css/pages/invoice-detail.css"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base = Path(settings.BASE_DIR)
        cls.template = (
            base / cls.template_relative
        ).read_text(encoding="utf-8-sig")
        cls.css = (
            base / cls.css_relative
        ).read_text(encoding="utf-8-sig")

    def test_overview_combines_stepper_summary_and_readiness(self):
        overview_start = self.template.index(
            'class="production-panel document-detail-overview"'
        )
        primary_start = self.template.index(
            'class="enterprise-detail-workspace"'
        )
        overview = self.template[overview_start:primary_start]

        for token in (
            "enterprise-document-stepper",
            "document-detail-overview-lower",
            "enterprise-document-summary",
            "enterprise-readiness-banner",
        ):
            self.assertIn(token, overview)

        self.assertEqual(
            self.template.count("document-detail-overview"),
            2,
        )
        self.assertIn(
            "{% if show_invoice_counterparty_primary_action %}",
            self.template,
        )
        self.assertNotIn(
            "{% if can_assign_counterparty %}",
            self.template,
        )
        self.assertIn("document-detail-title-row", self.template)
        self.assertIn("document-detail-status-badge", self.template)
        self.assertIn("document-workflow-current", self.template)
        self.assertIn("Все документы", self.template)
        self.assertNotIn('<span class="production-kicker">Документ к оплате</span>', self.template)

    def test_original_precedes_review_and_danger_zone_is_last(self):
        data_position = self.template.index("document-data-panel")
        original_position = self.template.index("document-original-panel")
        review_position = self.template.index(
            "document-field-review-panel"
        )
        payment_position = self.template.index(
            "document-payment-panel"
        )
        activity_position = self.template.index(
            "document-activity-panel"
        )
        danger_position = self.template.index(
            "document-detail-danger-zone"
        )
        workspace_end = self.template.index(
            'id="delete-invoice-modal"'
        )

        self.assertLess(data_position, original_position)
        self.assertLess(original_position, review_position)
        self.assertLess(review_position, payment_position)
        self.assertLess(payment_position, activity_position)
        self.assertLess(activity_position, danger_position)
        self.assertLess(danger_position, workspace_end)
        self.assertIn('data-modal-open="delete-invoice-modal"', self.template)
        self.assertIn('id="delete-invoice-modal"', self.template)
        self.assertIn("document-delete-confirm-form", self.template)
        self.assertNotIn('class="document-danger-form"', self.template)

    def test_field_review_uses_direct_modal_actions_without_intermediary_layers(self):
        for token in (
            "document-field-review-panel",
            "field-review-status-static",
            "field-review-row-action",
            'data-modal-open="field-review-modal-',
            "field-review-modal-position",
            'viewBox="0 0 24 24"',
            '<path d="m9 18 6-6-6-6"></path>',
        ):
            self.assertIn(token, self.template)

        for forbidden in (
            'id="field-review-drawer"',
            'data-drawer-open="field-review-drawer"',
            "field-review-open-button",
            "field-review-drawer-",
            "field-review-popover",
            "field-review-status-button",
            "data-popover-toggle=",
        ):
            self.assertNotIn(forbidden, self.template)

        for token in (
            ".document-field-review-panel",
            ".verification-row",
            "minmax(110px, auto)",
            ".field-review-status-static",
            ".field-review-row-action",
            ".field-review-row-action svg",
            "min-width: 112px",
            "white-space: nowrap",
        ):
            self.assertIn(token, self.css)

        for forbidden in (
            "#field-review-drawer",
            ".field-review-drawer",
            ".field-review-popover",
            ".field-review-open-button",
            ".field-review-status-button",
        ):
            self.assertNotIn(forbidden, self.css)

    def test_readiness_reasons_are_collapsed_disclosure(self):
        match = re.search(
            r"<details\s+class=\"readiness-issues-disclosure\"(?P<attrs>[^>]*)>",
            self.template,
        )
        self.assertIsNotNone(match)
        self.assertNotIn("open", match.group("attrs"))
        self.assertIn("Причины и предупреждения", self.template)
        self.assertIn(
            ".readiness-issues-disclosure[open] .readiness-issues-chevron",
            self.css,
        )

    def test_history_is_collapsed_and_comments_remain_available(self):
        history = re.search(
            r"<details\s+class=\"document-history-disclosure\"(?P<attrs>[^>]*)>",
            self.template,
        )
        comments = re.search(
            r"<details\s+class=\"document-comments-disclosure\"(?P<attrs>[^>]*)>",
            self.template,
        )

        self.assertIsNotNone(history)
        self.assertNotIn("open", history.group("attrs"))
        self.assertIsNotNone(comments)
        self.assertIn("open", comments.group("attrs"))

    def test_desktop_uses_balanced_primary_and_secondary_grids(self):
        for token in (
            ".document-detail-primary-grid",
            "minmax(420px, .95fr)",
            "align-items: start",
            ".document-detail-secondary-grid",
            "minmax(0, 1.04fr)",
            ".enterprise-detail-main",
            "gap: 18px",
            ".document-preview-frame",
            "min-height: 320px",
            "height: 320px",
            ".field-review-modal",
            "width: min(520px, calc(100vw - 32px))",
            ".field-review-modal-surface",
            ".document-danger-zone",
            "max-width: 520px",
            "margin-left: auto",
        ):
            self.assertIn(token, self.css)

        self.assertNotIn(
            "grid-template-columns: minmax(0, 1fr) minmax(420px, .95fr);",
            self.css,
        )
        self.assertNotIn(
            ".document-data-panel,\n.document-original-panel {\n"
            "    height: 100%;\n}",
            self.css,
        )

    def test_tablet_and_mobile_keep_compact_business_order(self):
        for token in (
            "@media (max-width: 1080px)",
            ".document-detail-primary-grid",
            ".document-detail-secondary-grid",
            "height: 360px",
            "@media (max-width: 900px)",
            "grid-template-columns: repeat(2, minmax(0, 1fr))",
            ".field-review-field-name",
            "@media (max-width: 760px)",
            "grid-template-columns: repeat(5, minmax(0, 1fr))",
            ".enterprise-document-stepper div",
            "min-width: 0",
            "overflow: visible",
            ".document-workflow-current",
            ".field-review-current",
            ".field-review-recognized",
            'content: "Система"',
            'content: "Документ"',
            ".field-review-modal",
            "width: min(520px, calc(100vw - 24px))",
            "max-width: 520px",
            "height: auto",
            "max-height: calc(100dvh - 24px)",
            ".field-review-modal[open]",
            "place-items: center",
            ".field-review-modal-surface",
            "min-height: 0",
            ".field-review-confirm-form",
            "display: flex",
            "flex-direction: column",
            ".field-review-compare-grid > div",
            "align-content: start",
            ".field-review-modal .z-modal-header",
            "position: static",
            ".field-review-modal .z-modal-footer",
            "margin-inline: -16px",
            "margin-bottom: -16px",
            ".field-review-modal .z-modal-footer .btn",
            "min-height: 44px",
            "height: auto",
            "env(safe-area-inset-bottom)",
            ".document-uploaded-by-fact",
            ".document-file-fact",
            "grid-column: 1 / -1",
            "height: 280px",
        ):
            self.assertIn(token, self.css)

        self.assertIn(
            'class="document-uploaded-by-fact"',
            self.template,
        )
        self.assertNotIn("overflow-x: auto", self.css)
        self.assertNotRegex(
            self.css,
            r"(?m)^\\s*bottom:\\s*-16px;\\s*$",
        )
        self.assertNotIn("margin: 0 -16px -16px", self.css)
        self.assertNotIn("width: 100vw", self.css)
        self.assertNotIn("height: 100dvh", self.css)
        self.assertNotIn("min-height: 100dvh", self.css)
        self.assertNotIn("max-height: 100dvh", self.css)
        self.assertNotIn("place-items: stretch", self.css)
        self.assertNotIn("margin: auto -16px -16px", self.css)
        self.assertNotIn(
            ".enterprise-original-column {\n        position: sticky",
            self.css,
        )

    def test_page_owner_css_has_no_patch_techniques(self):
        self.assertNotIn("!important", self.css)
        self.assertNotIn("nth-child(", self.css)
        self.assertNotIn("rgba(", self.css.lower())
        self.assertNotIn("@supports", self.css)
        self.assertNotIn(":has(", self.css)
        self.assertNotIn("translateX(", self.css)
        self.assertNotIn(".field-review-info-button", self.css)
        self.assertNotIn(".document-danger-form", self.css)
        self.assertNotIn("#field-review-drawer", self.css)
        self.assertNotIn(".field-review-drawer", self.css)
        self.assertNotIn(".field-review-popover", self.css)
        self.assertNotIn(".field-review-open-button", self.css)
        self.assertNotIn(".field-review-status-button", self.css)
        self.assertNotIn(".document-danger-copy span", self.css)
        self.assertNotIn("Подтвердить итоговое значение", self.template)
        self.assertNotIn(">\n                        ×\n                    </button>", self.template)
        self.assertNotIn("min-height: 500px", self.css)
        self.assertNotIn("height: 440px", self.css)
        self.assertNotRegex(
            self.css,
            r"\.(?:enterprise-document-detail|document-detail-primary-grid)"
            r"[^{]*\{[^}]*position\s*:\s*absolute",
        )
