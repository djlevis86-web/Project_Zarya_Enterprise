from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice


class InvoiceQuickUpdateTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.staff = User.objects.create_user(
            username='quick-update-staff',
            email='quick-update-staff@example.com',
            password='pass',
            is_staff=True,
        )

        self.user = User.objects.create_user(
            username='quick-update-user',
            email='quick-update-user@example.com',
            password='pass',
        )

        self.invoice = Invoice.objects.create(
            user=self.user,
            title='Быстрое редактирование',
            amount=Decimal('1000.00'),
            status=Invoice.STATUS_NEW,
            planned_payment_date=date(2026, 7, 10),
        )

    def test_staff_can_quick_update_status_and_planned_payment_date(self):
        self.client.force_login(
            self.staff
        )

        next_url = '/invoices/?search=fast&page=2&status=new'

        response = self.client.post(
            reverse(
                'quick_update_invoice',
                args=[
                    self.invoice.id,
                ]
            ),
            {
                'status': Invoice.STATUS_APPROVED,
                'planned_payment_date': '2026-07-25',
                'next': next_url,
            }
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertEqual(
            response['Location'],
            next_url,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.STATUS_APPROVED,
        )
        self.assertEqual(
            self.invoice.planned_payment_date,
            date(2026, 7, 25),
        )

    def test_quick_update_rejects_invalid_planned_payment_date(self):
        self.client.force_login(
            self.staff
        )

        response = self.client.post(
            reverse(
                'quick_update_invoice',
                args=[
                    self.invoice.id,
                ]
            ),
            {
                'status': Invoice.STATUS_APPROVED,
                'planned_payment_date': 'bad-date',
                'next': '/invoices/',
            }
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.STATUS_NEW,
        )
        self.assertEqual(
            self.invoice.planned_payment_date,
            date(2026, 7, 10),
        )

    def test_non_staff_cannot_quick_update_invoice(self):
        self.client.force_login(
            self.user
        )

        response = self.client.post(
            reverse(
                'quick_update_invoice',
                args=[
                    self.invoice.id,
                ]
            ),
            {
                'status': Invoice.STATUS_APPROVED,
                'planned_payment_date': '2026-07-25',
                'next': '/invoices/',
            }
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.STATUS_NEW,
        )
        self.assertEqual(
            self.invoice.planned_payment_date,
            date(2026, 7, 10),
        )
