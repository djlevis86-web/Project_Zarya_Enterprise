from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.document_field_review_service import (
    build_invoice_field_review_workspace,
)
from invoices.models import Counterparty, Invoice, InvoiceFieldReview


class DocumentFieldReviewInteractionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="interaction-staff",
            email="interaction-staff@example.com",
            password="test-password",
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="interaction-regular",
            email="interaction-regular@example.com",
            password="test-password",
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО Справочник",
            full_name="Общество с ограниченной ответственностью Справочник",
            inn="7700000000",
            kpp="770001001",
            source=Counterparty.SOURCE_1C,
        )
        self.invoice = Invoice.objects.create(
            user=self.staff,
            title="Документ V19",
            file="invoices/interaction-v19.pdf",
            original_filename="interaction-v19.pdf",
            amount=Decimal("1300.00"),
            ocr_amount=Decimal("1250.00"),
            amount_verified=False,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            invoice_number="SYS-42",
            document_date=date(2026, 7, 3),
            invoice_date="03.07.2026",
            vendor="ООО Итог",
            counterparty=self.counterparty,
            status=Invoice.STATUS_IN_WORK,
        )
        now = timezone.now()
        self.reviews = {
            InvoiceFieldReview.FIELD_AMOUNT: InvoiceFieldReview.objects.create(
                invoice=self.invoice,
                field_name=InvoiceFieldReview.FIELD_AMOUNT,
                recognized_value="1250.00",
                recognized_source=InvoiceFieldReview.SOURCE_OCR,
                current_value="1300.00",
            ),
            InvoiceFieldReview.FIELD_INVOICE_NUMBER: InvoiceFieldReview.objects.create(
                invoice=self.invoice,
                field_name=InvoiceFieldReview.FIELD_INVOICE_NUMBER,
                recognized_value="DOC-42",
                recognized_source=InvoiceFieldReview.SOURCE_OCR,
                current_value="SYS-42",
            ),
            InvoiceFieldReview.FIELD_DOCUMENT_DATE: InvoiceFieldReview.objects.create(
                invoice=self.invoice,
                field_name=InvoiceFieldReview.FIELD_DOCUMENT_DATE,
                recognized_value="2026-07-02",
                recognized_source=InvoiceFieldReview.SOURCE_OCR,
                current_value="2026-07-03",
                confirmed_value="2026-07-03",
                is_confirmed=True,
                confirmed_by=self.staff,
                confirmed_at=now,
            ),
            InvoiceFieldReview.FIELD_VENDOR: InvoiceFieldReview.objects.create(
                invoice=self.invoice,
                field_name=InvoiceFieldReview.FIELD_VENDOR,
                recognized_value="ООО Из документа",
                recognized_source=InvoiceFieldReview.SOURCE_OCR,
                current_value="ООО Итог",
                confirmed_value="ООО Итог",
                is_confirmed=True,
                confirmed_by=self.staff,
                confirmed_at=now,
            ),
        }

    def test_staff_detail_renders_v19_review_interactions(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("invoice_detail", kwargs={"invoice_id": self.invoice.id})
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('data-interaction-contract="v19"', html)
        self.assertIn('id="field-review-drawer"', html)
        self.assertIn('data-drawer-open="field-review-drawer"', html)
        self.assertIn('id="field-review-modal-amount"', html)
        self.assertIn('id="field-review-popover-invoice_number"', html)
        self.assertEqual(html.count("data-field-review-row="), 4)
        self.assertContains(response, "1 300,00 ₽")
        self.assertContains(response, "1 250,00 ₽")
        self.assertContains(response, "DOC-42")
        self.assertContains(response, "ООО Из документа")
        self.assertContains(response, "Справочник 1С")
        self.assertContains(
            response,
            "Общество с ограниченной ответственностью Справочник",
        )
        self.assertContains(response, "2/4 подтверждено")
        self.assertContains(
            response,
            reverse(
                "confirm_invoice_field",
                kwargs={
                    "invoice_id": self.invoice.id,
                    "field_name": InvoiceFieldReview.FIELD_AMOUNT,
                },
            ),
        )
        self.assertNotContains(response, "OCR")
        self.assertNotIn("onclick=", html)
        self.assertNotIn("onsubmit=", html)

    def test_regular_user_sees_review_data_without_confirmation_forms(self):
        self.invoice.user = self.regular
        self.invoice.save(update_fields=("user", "updated_at"))
        self.client.force_login(self.regular)

        response = self.client.get(
            reverse("invoice_detail", kwargs={"invoice_id": self.invoice.id})
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertEqual(html.count("data-field-review-row="), 4)
        self.assertContains(response, "Только просмотр", count=4)
        self.assertNotIn("data-modal-open=", html)
        self.assertNotIn("field-review-confirm-form", html)

    def test_missing_review_rows_are_presented_without_get_side_effects(self):
        InvoiceFieldReview.objects.filter(invoice=self.invoice).delete()
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("invoice_detail", kwargs={"invoice_id": self.invoice.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            InvoiceFieldReview.objects.filter(invoice=self.invoice).count(),
            0,
        )
        self.assertEqual(
            response.content.decode("utf-8").count("data-field-review-row="),
            4,
        )

    def test_workspace_reports_confirmed_and_attention_counts(self):
        workspace = build_invoice_field_review_workspace(
            self.invoice,
            InvoiceFieldReview.objects.filter(invoice=self.invoice).select_related(
                "confirmed_by"
            ),
        )

        self.assertEqual(workspace["total_count"], 4)
        self.assertEqual(workspace["confirmed_count"], 2)
        self.assertEqual(workspace["attention_count"], 2)
        rows = {row["field_name"]: row for row in workspace["rows"]}
        self.assertEqual(rows["amount"]["status_code"], "mismatch")
        self.assertEqual(rows["document_date"]["status_code"], "confirmed")
        self.assertEqual(rows["document_date"]["input_type"], "date")

    def test_confirmation_redirect_renders_success_toast(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse(
                "confirm_invoice_field",
                kwargs={
                    "invoice_id": self.invoice.id,
                    "field_name": InvoiceFieldReview.FIELD_AMOUNT,
                },
            ),
            {
                "value": "1300.00",
                "next": reverse(
                    "invoice_detail",
                    kwargs={"invoice_id": self.invoice.id},
                ),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Поле документа подтверждено.")
        self.assertContains(response, "data-toast")
        self.assertContains(response, "data-toast-close")


class InteractionLayerStaticContractTests(TestCase):
    def test_global_interaction_assets_are_local_and_wired(self):
        base = Path(settings.BASE_DIR)
        template = (base / "templates/base.html").read_text(encoding="utf-8-sig")
        css = (base / "static/css/components/modals.css").read_text(
            encoding="utf-8-sig"
        )
        runtime = (base / "static/js/interaction-layer-v1.js").read_text(
            encoding="utf-8-sig"
        )
        detail = (base / "templates/invoices/detail.html").read_text(
            encoding="utf-8-sig"
        )
        accessibility = (
            base / "static/css/base/accessibility.css"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("interaction-layer-v1.js", template)
        self.assertIn("data-toast-region", template)
        for token in (".z-modal", ".z-drawer", ".z-popover", ".z-toast"):
            self.assertIn(token, css)
        self.assertRegex(
            css,
            r"\.z-drawer\[hidden\]\s*\{[^}]*display\s*:\s*none\s*;?[^}]*\}",
        )
        self.assertIn('id="field-review-drawer"', detail)
        self.assertRegex(
            detail,
            r'id="field-review-drawer"[\s\S]*?data-drawer[\s\S]*?aria-hidden="true"[\s\S]*?hidden',
        )
        for token in (
            "data-modal-open",
            "data-drawer-open",
            "data-popover-toggle",
            "data-toast-close",
        ):
            self.assertIn(token, runtime)
            self.assertIn(token, template + detail)
        self.assertNotIn("http://", runtime)
        self.assertNotIn("https://", runtime)
        self.assertNotIn("onclick=", detail)
        self.assertNotIn("onsubmit=", detail)
        self.assertIn('class="skip-link"', template)
        self.assertIn('id="main-content"', template)
        self.assertGreaterEqual(template.count('aria-current="page"'), 10)
        self.assertIn(":focus-visible", accessibility)
        self.assertIn("prefers-reduced-motion", accessibility)
