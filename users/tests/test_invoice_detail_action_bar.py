from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from invoices.invoice_action_context import (
    get_invoice_detail_action_context,
)
from invoices.models import Invoice


class InvoiceDetailActionBarRenderTests(
    TestCase
):
    def setUp(self):
        User = get_user_model()

        self.admin = User.objects.create_user(
            username="action-bar-admin",
            email="action-bar-admin@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        self.owner = User.objects.create_user(
            username="action-bar-owner",
            email="action-bar-owner@example.com",
            password="pass12345",
            role=User.Role.USER,
            is_staff=False,
            is_superuser=False,
        )

        self.invoice = Invoice.objects.create(
            user=self.owner,
            title="Production action bar invoice",
            file="invoices/action-bar.pdf",
            amount=Decimal("1000.00"),
            status=Invoice.STATUS_NEW,
        )

        self.detail_url = reverse(
            "invoice_detail",
            args=[self.invoice.id],
        )

    def test_admin_sees_production_action_bar(
        self,
    ):
        self.client.force_login(
            self.admin
        )

        response = self.client.get(
            self.detail_url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        for context_key in (
            "can_edit_invoice",
            "can_assign_invoice_counterparty",
            "show_invoice_counterparty_primary_action",
            "can_process_invoice_ocr",
            "can_delete_invoice",
            "show_invoice_action_menu",
        ):
            with self.subTest(
                context_key=context_key
            ):
                self.assertTrue(
                    response.context[
                        context_key
                    ]
                )

        self.assertContains(
            response,
            "invoice-detail-production-action-bar",
        )
        self.assertContains(
            response,
            'aria-haspopup="menu"',
        )
        self.assertContains(
            response,
            'role="menu"',
        )
        self.assertContains(
            response,
            'role="menuitem"',
            count=3,
        )
        self.assertContains(
            response,
            "Привязать контрагента",
        )
        self.assertContains(
            response,
            "Повторить OCR",
        )
        self.assertContains(
            response,
            "Поставить OCR в очередь",
        )
        self.assertContains(
            response,
            "Удалить документ",
        )

        for url in (
            reverse(
                "edit_invoice",
                args=[self.invoice.id],
            ),
            reverse(
                "invoice_assign_counterparty",
                args=[self.invoice.id],
            ),
            reverse(
                "repeat_ocr",
                args=[self.invoice.id],
            ),
            reverse(
                "delete_invoice",
                args=[self.invoice.id],
            ),
            reverse(
                "enqueue_ocr_jobs"
            ),
        ):
            with self.subTest(url=url):
                self.assertContains(
                    response,
                    url,
                )

    def test_regular_owner_sees_navigation_without_management_actions(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.detail_url
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertFalse(
            response.context[
                "show_invoice_action_bar"
            ]
        )
        self.assertFalse(
            response.context[
                "show_invoice_action_menu"
            ]
        )
        self.assertFalse(
            response.context[
                "can_assign_invoice_counterparty"
            ]
        )

        self.assertContains(
            response,
            "invoice-detail-back-link",
        )
        self.assertNotContains(
            response,
            "invoice-detail-production-action-bar",
        )

        for url in (
            reverse(
                "edit_invoice",
                args=[self.invoice.id],
            ),
            reverse(
                "invoice_assign_counterparty",
                args=[self.invoice.id],
            ),
            reverse(
                "repeat_ocr",
                args=[self.invoice.id],
            ),
            reverse(
                "delete_invoice",
                args=[self.invoice.id],
            ),
        ):
            with self.subTest(url=url):
                self.assertNotContains(
                    response,
                    url,
                )

    def test_counterparty_action_label_reflects_document_state(
        self,
    ):
        assigned_context = (
            get_invoice_detail_action_context(
                self.admin,
                SimpleNamespace(
                    counterparty_id=42
                ),
            )
        )

        missing_context = (
            get_invoice_detail_action_context(
                self.admin,
                SimpleNamespace(
                    counterparty_id=None
                ),
            )
        )

        self.assertTrue(
            assigned_context[
                "show_invoice_counterparty_menu_action"
            ]
        )
        self.assertFalse(
            assigned_context[
                "show_invoice_counterparty_primary_action"
            ]
        )
        self.assertTrue(
            missing_context[
                "show_invoice_counterparty_primary_action"
            ]
        )
        self.assertFalse(
            missing_context[
                "show_invoice_counterparty_menu_action"
            ]
        )



class InvoiceDetailActionBarStaticTests(
    SimpleTestCase
):
    @staticmethod
    def read(
        relative_path: str,
    ) -> str:
        return (
            Path(settings.BASE_DIR)
            / relative_path
        ).read_text(
            encoding="utf-8-sig"
        ).replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

    def test_action_bar_has_single_production_owner(
        self,
    ):
        app_css = self.read(
            "static/css/app.css"
        )
        action_css = self.read(
            (
                "static/css/features/"
                "invoice-detail-action-bar.css"
            )
        )
        page_header_css = self.read(
            (
                "static/css/features/"
                "page-header-visual-v1.css"
            )
        )
        invoice_css = self.read(
            "static/css/pages/invoice-detail.css"
        )

        import_line = (
            '@import "./features/'
            'invoice-detail-action-bar.css";'
        )

        self.assertEqual(
            app_css.count(import_line),
            1,
        )
        self.assertGreater(
            app_css.index(import_line),
            app_css.index(
                (
                    '@import "./features/'
                    'page-header-visual-v1.css";'
                )
            ),
        )

        for marker in (
            (
                "INVOICE-DETAIL-PRODUCTION-"
                "ACTION-BAR-START"
            ),
            (
                "INVOICE-DETAIL-PRODUCTION-"
                "ACTION-BAR-END"
            ),
        ):
            with self.subTest(marker=marker):
                self.assertEqual(
                    action_css.count(marker),
                    1,
                )

        self.assertNotIn(
            (
                "INVOICE-DETAIL-MOBILE-"
                "ACTIONS-V1-2"
            ),
            page_header_css,
        )
        self.assertNotIn(
            (
                ".invoice-detail-page-v1 "
                ".invoice-detail-actions-v1 {"
            ),
            invoice_css,
        )
        self.assertNotIn(
            "!important",
            action_css,
        )
        self.assertNotIn(
            "nth-child(",
            action_css,
        )
        self.assertNotRegex(
            action_css,
            r"(?m)^\s*order\s*:",
        )
        self.assertIn(
            ".invoice-detail-action-counterparty",
            action_css,
        )
        self.assertIn(
            (
                'class="invoice-detail-action-menu-item '
                'btn-danger"'
            ),
            self.read(
                "templates/invoices/detail.html"
            ),
        )
        self.assertNotRegex(
            action_css,
            (
                r"#[0-9a-fA-F]{3,8}\b"
                r"|rgba?\([^)]*\)"
                r"|hsla?\([^)]*\)"
            ),
        )

    def test_action_menu_script_is_accessible_and_page_specific(
        self,
    ):
        base_template = self.read(
            "templates/base.html"
        )
        detail_template = self.read(
            "templates/invoices/detail.html"
        )
        script = self.read(
            (
                "static/js/"
                "invoice-detail-action-menu.js"
            )
        )

        self.assertEqual(
            base_template.count(
                "{% block extra_js %}"
            ),
            1,
        )
        self.assertEqual(
            detail_template.count(
                "{% block extra_js %}"
            ),
            1,
        )
        self.assertEqual(
            detail_template.count(
                (
                    "js/"
                    "invoice-detail-action-menu.js"
                )
            ),
            1,
        )

        for contract in (
            "aria-expanded",
            "ArrowDown",
            "ArrowUp",
            "Home",
            "End",
            "Escape",
            "pointerdown",
            "window.confirm",
            "restoreFocus",
        ):
            with self.subTest(
                script_contract=contract
            ):
                self.assertIn(
                    contract,
                    script,
                )

        self.assertNotIn(
            "innerHTML",
            script,
        )
        self.assertNotIn(
            "eval(",
            script,
        )
        self.assertNotRegex(
            detail_template,
            r"\bonsubmit\s*=",
        )
