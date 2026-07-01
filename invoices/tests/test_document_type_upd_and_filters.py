from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice
from ocr.services import detect_document_type, parse_invoice_data


class DocumentTypeOCRTests(TestCase):
    def test_detects_upd_text(self):
        self.assertEqual(
            detect_document_type(
                "Универсальный передаточный документ № 123 от 01.07.2026"
            ),
            "upd",
        )

    def test_parse_invoice_data_returns_document_type_and_date(self):
        parsed = parse_invoice_data(
            "УПД № 123 от 01.07.2026\nВсего к оплате 1500,00\nИНН 3525447980"
        )

        self.assertEqual(parsed["document_type"], "upd")
        self.assertEqual(parsed["document_date"], date(2026, 7, 1))


class InvoiceListDocumentFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="document-user",
            email="document-user@example.com",
            password="pass12345",
            first_name="Иван",
            last_name="Петров",
            is_staff=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            title="Счёт для фильтра",
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            document_date=date(2026, 7, 1),
            planned_payment_date=date(2026, 7, 10),
            amount=Decimal("1000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
        )

        self.upd = Invoice.objects.create(
            user=self.user,
            title="УПД для фильтра",
            document_type=Invoice.DOCUMENT_TYPE_UPD,
            document_date=date(2026, 7, 5),
            planned_payment_date=date(2026, 7, 20),
            amount=Decimal("2000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
        )

    def test_filter_by_document_type_upd(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("invoice_list"),
            {"document_type": Invoice.DOCUMENT_TYPE_UPD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "УПД для фильтра")
        self.assertNotContains(response, "Счёт для фильтра")

    def test_filter_by_document_date_range(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("invoice_list"),
            {
                "document_date_from": "2026-07-04",
                "document_date_to": "2026-07-06",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "УПД для фильтра")
        self.assertNotContains(response, "Счёт для фильтра")

    def test_filter_by_planned_payment_date_range(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("invoice_list"),
            {
                "planned_payment_date_from": "2026-07-09",
                "planned_payment_date_to": "2026-07-11",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Счёт для фильтра")
        self.assertNotContains(response, "УПД для фильтра")

    def test_invoice_list_shows_uploader_name(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Загрузил")
        self.assertContains(response, "Иван Петров")
