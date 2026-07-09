from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.counterparty_service import get_or_create_counterparty_from_invoice
from invoices.models import Counterparty, Invoice


class CounterpartyOcrFallbackTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='counterparty-ocr-fallback-user',
            password='test-password',
        )

    def test_matches_single_counterparty_by_spaced_ocr_inn_without_filename(self):
        counterparty = Counterparty.objects.create(
            name='ЯРОСЛАВСКИЙ АПЦ АО',
            full_name='Акционерное общество "ЯРОСЛАВСКИЙ АГРАРНО-ПРОМЫШЛЕННЫЙ ЦЕНТР"',
            inn='7627049270',
            kpp='762701001',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        invoice = Invoice.objects.create(
            user=self.user,
            title='Документ без названия контрагента',
            original_filename='random-file.pdf',
            vendor=None,
            ocr_text=(
                'Покупатель ОАО "ЗАРЯ", ИНН 3507012256, КПП 350701001. '
                'Поставщик распознан плохо. '
                'Фрагмент OCR с разорванным ИНН поставщика: 7 627 049 270.'
            ),
        )

        found = get_or_create_counterparty_from_invoice(
            invoice
        )

        self.assertEqual(
            found,
            counterparty,
        )
        self.assertEqual(
            invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_FOUND,
        )
        self.assertIn(
            'без использования имени файла',
            invoice.counterparty_match_comment,
        )

    def test_does_not_match_by_original_filename(self):
        Counterparty.objects.create(
            name='ПАРТНЕРАВТО ООО',
            full_name='ООО "ПАРТНЕРАВТО"',
            inn='3525472432',
            kpp='352501001',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        invoice = Invoice.objects.create(
            user=self.user,
            title='Документ',
            original_filename='ПАРТНЕРАВТО.pdf',
            vendor=None,
            ocr_text='Счет без читаемых реквизитов поставщика.',
        )

        found = get_or_create_counterparty_from_invoice(
            invoice
        )

        self.assertIsNone(
            found
        )
        self.assertEqual(
            invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_NOT_FOUND,
        )

    def test_ambiguous_when_multiple_counterparties_found_by_spaced_ocr_inns(self):
        Counterparty.objects.create(
            name='Поставщик Один ООО',
            inn='1111111111',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )
        Counterparty.objects.create(
            name='Поставщик Два ООО',
            inn='2222222222',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        invoice = Invoice.objects.create(
            user=self.user,
            title='Документ',
            original_filename='random-file.pdf',
            vendor=None,
            ocr_text=(
                'Покупатель ОАО "ЗАРЯ", ИНН 3507012256. '
                'Плохо распознанные OCR-цифры: 1 111 111 111 и 2 222 222 222.'
            ),
        )

        found = get_or_create_counterparty_from_invoice(
            invoice
        )

        self.assertIsNone(
            found
        )
        self.assertEqual(
            invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_AMBIGUOUS,
        )
