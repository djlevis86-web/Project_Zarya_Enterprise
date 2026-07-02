from django.test import SimpleTestCase

from ocr.services import parse_amount


class TotalAmountSelectionTests(SimpleTestCase):

    def test_upd_total_payment_uses_amount_with_vat(self):
        text = """
        Всего к оплате 8 075,97 X 1 776,72 9 852,69
        """

        self.assertEqual(
            str(parse_amount(text)),
            "9852.69",
        )

    def test_invoice_total_ignores_contract_debt_amount(self):
        text = """
        Итого Руб:[13 380,33] 46 844,07] 254226,23]
        По состоянию на 22 июня 2026 года по договору поставки запасных частей
        числится задолженность в размере 1 514 495,95.
        """

        self.assertEqual(
            str(parse_amount(text)),
            "254226.23",
        )

    def test_total_with_vat_has_priority(self):
        text = """
        Итого: 173 490,00
        В т.ч. НДС: 16 608,78
        Итого с НДС: 173 490,00
        Всего наименований 3, на сумму 173 490,00 руб.
        """

        self.assertEqual(
            str(parse_amount(text)),
            "173490.00",
        )
