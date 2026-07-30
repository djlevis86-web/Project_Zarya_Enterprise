from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.models import Counterparty, Invoice, ResponsiblePerson
from invoices.presentation_services import (
    annotate_invoice_workspace,
    build_invoice_presentation,
)


class DocumentsPaymentsProductionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="production-staff",
            email="production@example.com",
            password="pass12345",
            is_staff=True,
            role=User.Role.MANAGER,
        )
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Смолина Елена",
            is_active=True,
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО ГОСКОМПЛЕКТ",
            inn="3525001001",
            bank_name="ТЕСТОВЫЙ БАНК",
            account_number="40702810000000000001",
            bik="044705615",
            is_active=True,
        )
        self.invoice = Invoice.objects.create(
            user=self.user,
            title="Телевизор",
            file="invoices/test.pdf",
            original_filename="invoice-617.pdf",
            amount=Decimal("14290.00"),
            ocr_amount=Decimal("14290.00"),
            amount_verified=True,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            invoice_number="617",
            document_date=date(2026, 7, 7),
            invoice_date="07.07.2026",
            vendor=self.counterparty.name,
            counterparty=self.counterparty,
            responsible=self.responsible,
            planned_payment_date=(
                timezone.localdate()
                + timedelta(days=7)
            ),
            status=Invoice.STATUS_APPROVED,
        )
        self.client.force_login(self.user)

    def test_dashboard_is_user_work_center(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Документы и платежи")
        self.assertContains(response, "Требуют проверки")
        self.assertContains(response, "К оплате сегодня")
        self.assertContains(response, "Ближайшие оплаты")
        self.assertNotContains(response, "Технический аудит")
        self.assertNotContains(response, "Отчёт бота")
        self.assertNotContains(response, "OCR")

    def test_invoice_list_uses_seven_business_columns(self):
        response = self.client.get(reverse("invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Счёт №617")
        self.assertContains(response, "ООО ГОСКОМПЛЕКТ")
        self.assertContains(response, "Готов к реестру")
        self.assertContains(response, "Ответственный")
        self.assertNotContains(response, "Повторить OCR")
        self.assertNotContains(response, "Поставить OCR")
        self.assertNotContains(response, "Удалить")
        html = response.content.decode("utf-8")
        header = html.split("<thead>", 1)[1].split("</thead>", 1)[0]
        self.assertEqual(header.count("<th"), 7)

    def test_detail_starts_with_legal_identity_and_payment_summary(self):
        response = self.client.get(
            reverse(
                "invoice_detail",
                kwargs={"invoice_id": self.invoice.id},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Счёт №617")
        self.assertContains(response, "Контрагент")
        self.assertContains(response, "Плановая дата")
        self.assertContains(response, "Оплачено")
        self.assertContains(response, "Остаток")
        self.assertContains(response, "Происхождение значений")
        self.assertContains(response, "Удаление документа")
        self.assertNotContains(response, "Повторить OCR")
        self.assertNotContains(response, "Поставить OCR")

    def test_legacy_approved_invalid_document_is_visible_as_repair(self):
        invoice = Invoice.objects.create(
            user=self.user,
            title="Некорректный документ",
            file="invoices/invalid.pdf",
            amount=Decimal("0.00"),
            amount_verified=False,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            status=Invoice.STATUS_APPROVED,
        )
        response = self.client.get(
            reverse(
                "invoice_detail",
                kwargs={"invoice_id": invoice.id},
            )
        )
        self.assertContains(response, "Требуется исправление")
        self.assertContains(response, "Не указана сумма к оплате")

    def test_presenter_uses_annotated_payment_data_without_extra_query(self):
        with self.assertNumQueries(1):
            invoice = annotate_invoice_workspace(
                Invoice.objects.filter(pk=self.invoice.pk)
            ).get()
        with self.assertNumQueries(0):
            presentation = build_invoice_presentation(invoice)
        self.assertEqual(presentation["title"], "Счёт №617")
        self.assertEqual(presentation["readiness_code"], "ready")


class DocumentsPaymentsStaticProductionTests(TestCase):
    def test_page_owners_are_final_and_old_patches_are_retired(self):
        base = Path(settings.BASE_DIR)
        app_css = (base / "static/css/app.css").read_text(encoding="utf-8-sig")
        self.assertNotIn("dashboard-page-header-visual-v1.css", app_css)
        self.assertNotIn("invoice-detail-action-bar.css", app_css)
        self.assertNotIn("invoice-list-table-responsive-v1.css", app_css)
        self.assertLess(app_css.index("./features/page-header-visual-v1.css"), app_css.index("./pages/dashboard.css"))
        self.assertLess(app_css.index("./pages/dashboard.css"), app_css.index("./pages/invoice-list.css"))
        self.assertLess(app_css.index("./pages/invoice-list.css"), app_css.index("./pages/invoice-detail.css"))

    def test_new_page_css_has_no_patch_techniques(self):
        base = Path(settings.BASE_DIR)
        for relative in (
            "static/css/pages/dashboard.css",
            "static/css/pages/invoice-list.css",
            "static/css/pages/invoice-detail.css",
        ):
            css = (base / relative).read_text(encoding="utf-8-sig")
            with self.subTest(relative=relative):
                self.assertNotIn("!important", css)
                self.assertNotIn("nth-child(", css)
                self.assertNotIn("#fff", css.lower())
                self.assertNotIn("rgba(", css.lower())

    def test_business_templates_do_not_expose_technical_actions(self):
        base = Path(settings.BASE_DIR)
        combined = "\n".join(
            (base / relative).read_text(encoding="utf-8-sig")
            for relative in (
                "templates/dashboard.html",
                "templates/invoices/invoice_list.html",
                "templates/invoices/detail.html",
            )
        )
        self.assertNotIn("Повторить OCR", combined)
        self.assertNotIn("Поставить OCR", combined)
        self.assertNotIn("Технический аудит", combined)
        self.assertNotIn("invoice-detail-action-menu", combined)
        self.assertNotIn("onclick=", combined)
        self.assertNotIn("onsubmit=", combined)
