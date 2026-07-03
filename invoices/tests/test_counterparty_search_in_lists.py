from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Counterparty, Invoice


class CounterpartySearchInListsTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.staff = User.objects.create_user(
            username='counterparty-list-search-staff',
            email='counterparty-list-search-staff@example.com',
            password='pass',
            is_staff=True,
            is_superuser=True,
        )

        self.user = User.objects.create_user(
            username='counterparty-list-search-user',
            email='counterparty-list-search-user@example.com',
            password='pass',
            is_staff=False,
        )

        self.counterparty = Counterparty.objects.create(
            name='БАЗА НЭТ',
            full_name='ООО БАЗА НЭТ',
            inn='7705551111',
            kpp='770501001',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.other_counterparty = Counterparty.objects.create(
            name='ДРУГОЙ ПОСТАВЩИК',
            full_name='ООО ДРУГОЙ ПОСТАВЩИК',
            inn='7805551111',
            kpp='780501001',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            counterparty=self.counterparty,
            title='Счёт от БАЗА НЭТ',
            amount=Decimal('1000.00'),
            status=Invoice.STATUS_APPROVED,
            amount_verified=True,
        )

        self.other_invoice = Invoice.objects.create(
            user=self.user,
            counterparty=self.other_counterparty,
            title='Счёт от другого поставщика',
            amount=Decimal('2000.00'),
            status=Invoice.STATUS_APPROVED,
            amount_verified=True,
        )

    def test_invoice_list_finds_uppercase_counterparty_by_lowercase_name(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse('invoice_list'),
            {
                'search': 'база',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'БАЗА НЭТ',
        )

        self.assertNotContains(
            response,
            'ДРУГОЙ ПОСТАВЩИК',
        )

    def test_invoice_list_finds_counterparty_by_inn(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse('invoice_list'),
            {
                'search': '7705551111',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'БАЗА НЭТ',
        )

        self.assertNotContains(
            response,
            'ДРУГОЙ ПОСТАВЩИК',
        )

    def test_payment_registry_finds_uppercase_counterparty_by_lowercase_name(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse('payment_registry'),
            {
                'status': Invoice.STATUS_APPROVED,
                'q': 'база',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'БАЗА НЭТ',
        )

        self.assertNotContains(
            response,
            'ДРУГОЙ ПОСТАВЩИК',
        )

    def test_payment_registry_finds_counterparty_by_inn(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse('payment_registry'),
            {
                'status': Invoice.STATUS_APPROVED,
                'q': '7705551111',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'БАЗА НЭТ',
        )

        self.assertNotContains(
            response,
            'ДРУГОЙ ПОСТАВЩИК',
        )

