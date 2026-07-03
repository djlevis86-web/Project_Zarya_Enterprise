from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Counterparty, Invoice


class CounterpartySearchAssignTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.staff = User.objects.create_user(
            username='counterparty-search-staff',
            email='counterparty-search-staff@example.com',
            password='pass',
            is_staff=True,
        )

        self.user = User.objects.create_user(
            username='counterparty-search-user',
            email='counterparty-search-user@example.com',
            password='pass',
            is_staff=False,
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            title='Счёт для поиска контрагента',
            amount=Decimal('5000.00'),
            status=Invoice.STATUS_NEW,
        )

        self.target = Counterparty.objects.create(
            name='ООО Ромашка',
            full_name='Общество с ограниченной ответственностью Ромашка',
            inn='7701234567',
            kpp='770101001',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.other = Counterparty.objects.create(
            name='ООО Василёк',
            full_name='Общество с ограниченной ответственностью Василёк',
            inn='7801234567',
            kpp='780101001',
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

    def test_assign_page_without_query_does_not_render_all_counterparties(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse(
                'invoice_assign_counterparty',
                args=[
                    self.invoice.id,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'Введите ИНН, КПП или название контрагента',
        )

        self.assertNotContains(
            response,
            self.target.name,
        )

        self.assertNotContains(
            response,
            self.other.name,
        )

    def test_search_counterparty_by_inn(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse(
                'invoice_assign_counterparty',
                args=[
                    self.invoice.id,
                ],
            ),
            {
                'q': '7701234567',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.target.name,
        )

        self.assertNotContains(
            response,
            self.other.name,
        )

    def test_search_counterparty_by_name(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.get(
            reverse(
                'invoice_assign_counterparty',
                args=[
                    self.invoice.id,
                ],
            ),
            {
                'q': 'Ромашка',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.target.name,
        )

        self.assertNotContains(
            response,
            self.other.name,
        )

    def test_staff_can_assign_counterparty_from_search_result(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.post(
            reverse(
                'invoice_assign_counterparty',
                args=[
                    self.invoice.id,
                ],
            ),
            {
                'q': '7701234567',
                'counterparty': self.target.id,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                'invoice_detail',
                args=[
                    self.invoice.id,
                ],
            ),
            fetch_redirect_response=False,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.counterparty,
            self.target,
        )

        self.assertEqual(
            self.invoice.counterparty_match_status,
            Invoice.COUNTERPARTY_MATCH_FOUND,
        )

    def test_inactive_counterparty_cannot_be_assigned(self):
        inactive = Counterparty.objects.create(
            name='ООО Архив',
            inn='9901234567',
            source=Counterparty.SOURCE_1C,
            is_active=False,
        )

        self.client.force_login(
            self.staff
        )

        response = self.client.post(
            reverse(
                'invoice_assign_counterparty',
                args=[
                    self.invoice.id,
                ],
            ),
            {
                'q': '9901234567',
                'counterparty': inactive.id,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'Выберите активного контрагента из 1С или ручного справочника.',
        )

        self.invoice.refresh_from_db()

        self.assertIsNone(
            self.invoice.counterparty,
        )
