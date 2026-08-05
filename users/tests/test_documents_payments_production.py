from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.audit_models import InvoiceLog
from invoices.models import (
    Counterparty,
    Invoice,
    InvoiceUploadBatch,
    PaymentRegistry,
    PaymentRegistryItem,
    ResponsiblePerson,
)
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
            planned_payment_date=(timezone.localdate() + timedelta(days=7)),
            status=Invoice.STATUS_APPROVED,
        )
        self.batch = InvoiceUploadBatch.objects.create(
            user=self.user,
            total_files=1,
            uploaded_count=1,
            status=InvoiceUploadBatch.STATUS_COMPLETED,
        )
        self.invoice.upload_batch = self.batch
        self.invoice.save(update_fields=["upload_batch", "updated_at"])
        self.registry = PaymentRegistry.objects.create(
            title="Реестр предприятия",
            created_by=self.user,
            items_count=1,
            total_amount=self.invoice.amount,
        )
        PaymentRegistryItem.objects.create(
            registry=self.registry,
            invoice=self.invoice,
            amount=self.invoice.amount,
            planned_payment_date=self.invoice.planned_payment_date,
        )
        InvoiceLog.objects.create(
            invoice=self.invoice,
            user=self.user,
            action="Документ загружен",
        )
        self.client.force_login(self.user)

    def test_dashboard_is_informative_enterprise_work_center(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        for text in (
            "Требует проверки",
            "К оплате сегодня",
            "Просрочено",
            "Готово к реестру",
            "Мои задачи",
            "График платежей",
            "Статусы документов",
            "Ближайшие платежи",
            "Последние действия",
        ):
            self.assertContains(response, text)
        self.assertContains(response, "enterprise-dashboard-data")
        self.assertNotContains(response, "Технический аудит")
        self.assertNotContains(response, "OCR")

    def test_invoice_list_uses_eight_enterprise_columns(self):
        response = self.client.get(reverse("invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Счёт №617")
        self.assertContains(response, "Сумма / остаток")
        self.assertContains(response, "Статус")
        self.assertContains(response, "Готовность")
        html = response.content.decode("utf-8")
        header = html.split("<thead>", 1)[1].split("</thead>", 1)[0]
        self.assertEqual(header.count("<th"), 8)
        self.assertNotContains(response, "Повторить OCR")

    def test_upload_and_journal_use_enterprise_process_contract(self):
        upload = self.client.get(reverse("upload_invoice"))
        journal = self.client.get(reverse("upload_batches"))
        detail = self.client.get(reverse("upload_batch_detail", kwargs={"batch_id": self.batch.id}))
        for response in (upload, journal, detail):
            self.assertEqual(response.status_code, 200)
        self.assertContains(upload, "Что происходит после загрузки")
        self.assertContains(upload, "Распознавание данных")
        self.assertContains(journal, "Контроль партий")
        self.assertContains(journal, "Дубликатов")
        self.assertContains(detail, "Результат загрузки")
        self.assertNotContains(upload, "OCR")

    def test_payment_schedule_has_kpi_chart_and_largest_payments(self):
        response = self.client.get(reverse("payment_schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Платёжный календарь")
        self.assertContains(
            response,
            "Платежи с назначенной датой",
        )
        self.assertContains(
            response,
            "Крупнейшие обязательства",
        )
        self.assertContains(response, "На графике")
        self.assertNotContains(response, "По дням, ₽")
        self.assertContains(response, "enterprise-schedule-data")

    def test_registry_has_lifecycle_check_and_queue(self):
        response = self.client.get(reverse("payment_registry"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Подготовка и контроль оплаты")
        self.assertContains(response, "Черновик")
        self.assertContains(response, "Состав текущего реестра")
        self.assertContains(response, "Очередь документов")

    def test_registry_detail_uses_enterprise_lifecycle(self):
        response = self.client.get(reverse("payment_registry_detail", kwargs={"registry_id": self.registry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Документы реестра")
        self.assertContains(response, "Выгружен")
        self.assertContains(response, "Частично оплачен")

    def test_detail_starts_with_workflow_identity_and_payment_summary(self):
        response = self.client.get(reverse("invoice_detail", kwargs={"invoice_id": self.invoice.id}))
        self.assertEqual(response.status_code, 200)
        for text in (
            "Счёт №617",
            "Новый",
            "В работе",
            "На согласовании",
            "Утверждён",
            "Оплачен",
            "Система и оригинал",
            "Состояние и история оплат",
            "Удаление документа",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "Повторить OCR")

    def test_missing_number_uses_business_fallback_and_hides_ocr(self):
        invoice = Invoice.objects.create(
            user=self.user,
            title="Документ для проверки",
            file="invoices/missing-number.pdf",
            amount=Decimal("0.00"),
            amount_verified=False,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            status=Invoice.STATUS_APPROVED,
        )
        InvoiceLog.objects.create(invoice=invoice, user=self.user, action="OCR повторно выполнен массово")
        response = self.client.get(reverse("invoice_detail", kwargs={"invoice_id": invoice.id}))
        self.assertContains(response, "Счёт без номера")
        self.assertNotContains(response, f"Счёт #{invoice.id}")
        self.assertContains(response, "Сумма документа не подтверждена по оригиналу.")
        self.assertContains(response, "Повторная проверка данных выполнена")
        self.assertNotContains(response, "OCR")

    def test_presenter_uses_annotated_payment_data_without_extra_query(self):
        with self.assertNumQueries(1):
            invoice = annotate_invoice_workspace(Invoice.objects.filter(pk=self.invoice.pk)).get()
        with self.assertNumQueries(0):
            presentation = build_invoice_presentation(invoice)
        self.assertEqual(presentation["title"], "Счёт №617")


class DocumentsPaymentsStaticProductionTests(TestCase):
    def test_enterprise_page_owners_and_local_chart_runtime(self):
        base = Path(settings.BASE_DIR)
        app_css = (base / "static/css/app.css").read_text(encoding="utf-8-sig")
        self.assertIn("./pages/upload-workspace.css", app_css)
        self.assertIn("./components/documents-payments-workspace.css", app_css)
        runtime = (base / "static/js/enterprise-workspace.js").read_text(encoding="utf-8-sig")
        self.assertIn("data-enterprise-chart", runtime)
        self.assertNotIn("https://", runtime)
        self.assertNotIn("http://", runtime)

    def test_page_css_has_no_patch_techniques(self):
        base = Path(settings.BASE_DIR)
        for relative in (
            "static/css/pages/dashboard.css",
            "static/css/pages/invoice-list.css",
            "static/css/pages/payment-schedule.css",
            "static/css/pages/payment-registry.css",
            "static/css/pages/invoice-detail.css",
            "static/css/pages/upload-workspace.css",
        ):
            css = (base / relative).read_text(encoding="utf-8-sig")
            with self.subTest(relative=relative):
                self.assertNotIn("!important", css)
                self.assertNotIn("nth-child(", css)
                self.assertNotIn("rgba(", css.lower())

    def test_business_templates_do_not_expose_technical_actions(self):
        base = Path(settings.BASE_DIR)
        templates = (
            "templates/dashboard.html",
            "templates/invoices/invoice_list.html",
            "templates/invoices/upload_invoice.html",
            "templates/invoices/upload_batches.html",
            "templates/invoices/upload_batch_detail.html",
            "templates/invoices/payment_schedule.html",
            "templates/invoices/payment_registry.html",
            "templates/invoices/payment_registry_detail.html",
            "templates/invoices/detail.html",
        )
        combined = "\n".join((base / relative).read_text(encoding="utf-8-sig") for relative in templates)
        self.assertNotIn("Повторить OCR", combined)
        self.assertNotIn("Поставить OCR", combined)
        self.assertNotIn("OCR-", combined)
        self.assertNotIn("onclick=", combined)
        self.assertNotIn("onsubmit=", combined)

    def test_all_seven_screens_have_enterprise_contract(self):
        base = Path(settings.BASE_DIR)
        expected = {
            "templates/dashboard.html": "data-enterprise-screen=\"dashboard\"",
            "templates/invoices/invoice_list.html": "data-enterprise-screen=\"invoice-list\"",
            "templates/invoices/upload_invoice.html": "data-enterprise-screen=\"upload\"",
            "templates/invoices/upload_batches.html": "data-enterprise-screen=\"upload-journal\"",
            "templates/invoices/payment_schedule.html": "data-enterprise-screen=\"payment-schedule\"",
            "templates/invoices/payment_registry.html": "data-enterprise-screen=\"payment-registry\"",
            "templates/invoices/detail.html": "data-enterprise-screen=\"invoice-detail\"",
        }
        for relative, token in expected.items():
            with self.subTest(relative=relative):
                self.assertIn(token, (base / relative).read_text(encoding="utf-8-sig"))
