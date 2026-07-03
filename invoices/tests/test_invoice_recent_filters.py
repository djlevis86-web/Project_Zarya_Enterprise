from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice
from invoices.view_modules.invoice_list_views import RECENT_INVOICE_FILTERS_SESSION_KEY


class InvoiceRecentFiltersTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username='recent-filters-user',
            email='recent-filters-user@example.com',
            password='pass12345',
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            title='RECENT FILTER INVOICE',
            amount=Decimal('1000.00'),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            document_date=date(2026, 7, 1),
            planned_payment_date=date(2026, 7, 10),
        )

    def test_invoice_list_saves_recent_filter_in_session_and_shows_link(self):
        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse('invoice_list'),
            {
                'search': 'RECENT FILTER',
                'status': Invoice.STATUS_APPROVED,
                'document_type': Invoice.DOCUMENT_TYPE_INVOICE,
                'planned_payment_date_from': '2026-07-01',
                'planned_payment_date_to': '2026-07-31',
                'sort': 'id',
                'page': '2',
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        recent_filters = self.client.session.get(
            RECENT_INVOICE_FILTERS_SESSION_KEY
        )

        self.assertEqual(
            len(recent_filters),
            1,
        )
        self.assertIn(
            'search=RECENT+FILTER',
            recent_filters[0]['querystring'],
        )
        self.assertIn(
            'status=approved',
            recent_filters[0]['querystring'],
        )
        self.assertIn(
            'document_type=invoice',
            recent_filters[0]['querystring'],
        )
        self.assertIn(
            'planned_payment_date_from=2026-07-01',
            recent_filters[0]['querystring'],
        )
        self.assertIn(
            'planned_payment_date_to=2026-07-31',
            recent_filters[0]['querystring'],
        )
        self.assertIn(
            'sort=id',
            recent_filters[0]['querystring'],
        )
        self.assertNotIn(
            'page=2',
            recent_filters[0]['querystring'],
        )

        self.assertContains(
            response,
            'Последние поиски',
        )
        self.assertContains(
            response,
            'Поиск: RECENT FILTER',
        )

    def test_invoice_list_does_not_save_empty_filter(self):
        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse('invoice_list')
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIsNone(
            self.client.session.get(
                RECENT_INVOICE_FILTERS_SESSION_KEY
            )
        )

    def test_invoice_list_keeps_only_five_recent_filters_and_deduplicates(self):
        self.client.force_login(
            self.user
        )

        for index in range(6):
            self.client.get(
                reverse('invoice_list'),
                {
                    'search': f'RECENT-{index}',
                },
            )

        recent_filters = self.client.session.get(
            RECENT_INVOICE_FILTERS_SESSION_KEY
        )

        self.assertEqual(
            len(recent_filters),
            5,
        )
        self.assertIn(
            'RECENT-5',
            recent_filters[0]['label'],
        )
        self.assertNotIn(
            'RECENT-0',
            ' '.join(
                item['label']
                for item in recent_filters
            ),
        )

        self.client.get(
            reverse('invoice_list'),
            {
                'search': 'RECENT-3',
            },
        )

        recent_filters = self.client.session.get(
            RECENT_INVOICE_FILTERS_SESSION_KEY
        )

        self.assertEqual(
            len(recent_filters),
            5,
        )
        self.assertIn(
            'RECENT-3',
            recent_filters[0]['label'],
        )
        self.assertEqual(
            sum(
                1
                for item in recent_filters
                if 'RECENT-3' in item['label']
            ),
            1,
        )

    def test_clear_recent_invoice_filters_removes_session_key(self):
        self.client.force_login(
            self.user
        )

        self.client.get(
            reverse('invoice_list'),
            {
                'search': 'RECENT CLEAR',
            },
        )

        self.assertIsNotNone(
            self.client.session.get(
                RECENT_INVOICE_FILTERS_SESSION_KEY
            )
        )

        response = self.client.post(
            reverse('clear_recent_invoice_filters')
        )

        self.assertRedirects(
            response,
            reverse('invoice_list'),
        )
        self.assertIsNone(
            self.client.session.get(
                RECENT_INVOICE_FILTERS_SESSION_KEY
            )
        )

        response = self.client.get(
            reverse('invoice_list')
        )

        self.assertNotContains(
            response,
            'Последние поиски',
        )
