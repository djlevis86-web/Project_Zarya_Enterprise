from django.test import TestCase

from invoices.counterparty_service import (
    extract_inn,
    extract_kpp,
    find_counterparty_by_requisites,
)
from invoices.models import Counterparty


class SupplierRequisiteSelectionTests(TestCase):

    def test_prefers_1c_counterparty_inn_over_bad_first_ocr_inn(self):
        counterparty = Counterparty.objects.create(
            name="ИП АПЕКС ПЛЮС ООО",
            full_name='ООО "ИП "АПЕКС ПЛЮС"',
            inn="7805732867",
            kpp="780501001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        text = """
        Общество с ограниченной ответственностью "ИННОВАЦИОННОЕ ПРЕДПРИЯТИЕ "АПЕКС ПЛЮС"
        ИНН 7805732857 КПП 780501001 ОГРН 1187847261315

        Банк получателя
        ИНН 7805732867 КПП 780501001
        ООО "ИП "АПЕКС ПЛЮС"
        Получатель
        """

        self.assertEqual(
            extract_inn(text),
            "7805732867",
        )

        self.assertEqual(
            extract_kpp(text),
            "780501001",
        )

        self.assertEqual(
            find_counterparty_by_requisites("7805732867", "780501001"),
            counterparty,
        )

    def test_own_company_inn_is_never_selected_as_supplier(self):
        Counterparty.objects.create(
            name="ЗАРЯ ОАО",
            full_name='ОАО "ЗАРЯ"',
            inn="3507012256",
            kpp="350701001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        text = """
        Покупатель: ОАО "ЗАРЯ", ИНН 3507012256, КПП 350701001
        """

        self.assertIsNone(
            extract_inn(text)
        )

        self.assertIsNone(
            find_counterparty_by_requisites("3507012256", "350701001")
        )
