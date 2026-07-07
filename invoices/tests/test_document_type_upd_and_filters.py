from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice
from invoices.ocr_processing_service import apply_ocr_identity_to_invoice
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


    def test_parse_real_upd_invoice_text_from_white_clover(self):
        parsed = parse_invoice_data(
            """
            Универсальный Счет-фактура № 198 от 25 июня 2026 г.
            передаточный документ
            Продавец: ООО "БЕЛЫЙ КЛЕВЕР"
            Покупатель: ОАО "Заря"
            ИНН/КПП продавца: 5321188917/532101001
            Документ об отгрузке Универсальный передаточный документ, № 198 от 25.06.2026
            Всего к оплате (9) 136 363,64 X 13 636,36 150 000,00
            """
        )

        self.assertEqual(
            parsed["document_type"],
            "upd",
        )

        self.assertEqual(
            parsed["invoice_number"],
            "198",
        )

        self.assertEqual(
            parsed["document_date"],
            date(2026, 6, 25),
        )



    def test_parse_real_upd_invoice_text_extracts_vendor_and_requisites(self):
        parsed = parse_invoice_data(
            """
            Универсальный Счет-фактура № 198 от 25 июня 2026 г.
            передаточный документ
            Продавец: ООО "БЕЛЫЙ КЛЕВЕР" (2) Покупатель: ОАО "Заря" (6)
            ИННЖПП продавца: 5321188917/532101001
            Документ об отгрузке Универсальный передаточный документ, № 198 от 25.06.2026
            Всего к оплате (9) 136 363,64 X 13 636,36 150 000,00
            """
        )

        self.assertEqual(
            parsed["document_type"],
            "upd",
        )

        self.assertEqual(
            parsed["invoice_number"],
            "198",
        )

        self.assertEqual(
            parsed["document_date"],
            date(2026, 6, 25),
        )

        self.assertEqual(
            parsed["vendor"],
            "ООО БЕЛЫЙ КЛЕВЕР",
        )

        self.assertEqual(
            parsed["inn"],
            "5321188917",
        )

        self.assertEqual(
            parsed["kpp"],
            "532101001",
        )


    def test_detects_utility_payment_document_text(self):
        self.assertEqual(
            detect_document_type(
                "Платежный документ за Июнь 2026 г. "
                "Исполнитель услуг: ООО Аквалайн "
                "Получатель платежа"
            ),
            "payment_document",
        )

    def test_detects_utility_notice_text(self):
        self.assertEqual(
            detect_document_type(
                "Извещение на оплату ЖКУ Квитанция "
                "Получатель: МУП ЖКХ Новленское ВМО"
            ),
            "payment_document",
        )

    def test_detects_noisy_invoice_with_split_word(self):
        self.assertEqual(
            detect_document_type(
                "С чет на оплату № 433 от 04 июля 2026 "
                "Оплата данного счета означает согласие"
            ),
            "invoice",
        )

    def test_detects_noisy_invoice_with_i_sch_marker(self):
        self.assertEqual(
            detect_document_type(
                "IСч. № 711 Банк получателя ООО ЦЕНТР НТУиК"
            ),
            "invoice",
        )

    def test_parse_invoice_data_returns_payment_document_type(self):
        parsed = parse_invoice_data(
            "Платежный документ за Июнь 2026 г. "
            "Исполнитель услуг: ООО Аквалайн "
            "Получатель платежа "
            "Итого к оплате 115,57"
        )

        self.assertEqual(
            parsed["document_type"],
            "payment_document",
        )



    def test_detects_noisy_invoice_without_word_invoice_but_with_payment_number_and_date(self):
        self.assertEqual(
            detect_document_type(
                "оплату № Br30622001 от 22 июня 2026 г. "
                "Итого с НДС 43 342,34"
            ),
            "invoice",
        )

    def test_detects_noisy_invoice_with_payment_phrase_and_number_and_date(self):
        self.assertEqual(
            detect_document_type(
                "ще на оплату № Br3C0617003 от 17 июня 2026 г. "
                "Итого с НДС 27 328,44"
            ),
            "invoice",
        )

    def test_invoice_with_cargo_words_and_invoice_marker_stays_invoice(self):
        self.assertEqual(
            detect_document_type(
                "Счет на оплату № 77 от 01 июля 2026 "
                "Поставщик ООО Ромашка "
                "Грузоотправитель ООО Ромашка "
                "Грузополучатель ОАО Заря"
            ),
            "invoice",
        )



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

    def test_invoice_list_pagination_preserves_filters(self):
        for index in range(16):
            Invoice.objects.create(
                user=self.user,
                title=f"PAGINATIONFILTER {index:02d}",
                document_type=Invoice.DOCUMENT_TYPE_INVOICE,
                document_date=date(2026, 7, 1),
                planned_payment_date=date(2026, 7, 10),
                amount=Decimal("1000.00"),
                amount_verified=True,
                status=Invoice.STATUS_APPROVED,
            )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("invoice_list"),
            {
                "search": "PAGINATIONFILTER",
                "status": Invoice.STATUS_APPROVED,
                "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
                "planned_payment_date_from": "2026-07-01",
                "planned_payment_date_to": "2026-07-31",
                "sort": "id",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        html = response.content.decode("utf-8")

        self.assertIn(
            "?page=2&amp;search=PAGINATIONFILTER",
            html,
        )
        self.assertIn(
            "status=approved",
            html,
        )
        self.assertIn(
            "document_type=invoice",
            html,
        )
        self.assertIn(
            "planned_payment_date_from=2026-07-01",
            html,
        )
        self.assertIn(
            "planned_payment_date_to=2026-07-31",
            html,
        )
        self.assertIn(
            "sort=id",
            html,
        )

    def test_invoice_list_shows_amount_requires_manual_verification(self):
        self.invoice.ocr_amount = Decimal("1000.00")
        self.invoice.amount_verified = False
        self.invoice.save(
            update_fields=[
                "ocr_amount",
                "amount_verified",
            ]
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse("invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сумма требует проверки")

    def test_invoice_list_shows_uploader_name(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Загрузил")
        self.assertContains(response, "Иван Петров")


    def test_apply_ocr_identity_sets_payment_document_type(self):
        warning = apply_ocr_identity_to_invoice(
            self.invoice,
            {
                "invoice_number": None,
                "invoice_date": None,
                "document_date": None,
                "document_type": Invoice.DOCUMENT_TYPE_PAYMENT_DOCUMENT,
                "vendor": None,
            },
        )

        self.assertEqual(warning, "")
        self.assertEqual(
            self.invoice.document_type,
            Invoice.DOCUMENT_TYPE_PAYMENT_DOCUMENT,
        )



    def test_detects_waybill_text(self):
        self.assertEqual(
            detect_document_type(
                "Товарная накладная № 45 от 01.07.2026"
            ),
            "waybill",
        )

    def test_detects_unknown_document_type_for_supported_ocr_text_without_known_markers(self):
        self.assertEqual(
            detect_document_type(
                "Акт сверки взаимных расчетов за период июль 2026"
            ),
            "unknown",
        )

    def test_parse_invoice_data_returns_waybill_document_type(self):
        parsed = parse_invoice_data(
            "Товарная накладная № 45 от 01.07.2026\n"
            "Поставщик: ООО РОМАШКА\n"
            "Грузополучатель: ОАО ЗАРЯ\n"
            "Итого 1250,00"
        )

        self.assertEqual(
            parsed["document_type"],
            "waybill",
        )
        self.assertEqual(
            parsed["invoice_number"],
            "45",
        )
        self.assertEqual(
            parsed["amount"],
            "1250.00",
        )

    def test_invoice_model_has_waybill_and_unknown_document_type_choices(self):
        self.assertIn(
            (
                Invoice.DOCUMENT_TYPE_WAYBILL,
                "Товарная накладная",
            ),
            Invoice.DOCUMENT_TYPE_CHOICES,
        )
        self.assertIn(
            (
                Invoice.DOCUMENT_TYPE_UNKNOWN,
                "Неизвестный тип",
            ),
            Invoice.DOCUMENT_TYPE_CHOICES,
        )
