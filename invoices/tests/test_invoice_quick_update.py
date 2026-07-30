from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import (
    Counterparty,
    Invoice,
    ResponsiblePerson,
)


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

    def test_staff_cannot_quick_approve_incomplete_document(self):
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
            Invoice.STATUS_NEW,
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

    def test_staff_can_quick_approve_complete_document(self):
        counterparty = Counterparty.objects.create(
            name="ГОТОВЫЙ ПОСТАВЩИК",
            inn="3525001001",
            bank_name="ТЕСТОВЫЙ БАНК",
            account_number="40702810000000000001",
            bik="044705615",
            source=Counterparty.SOURCE_1C,
        )
        responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный за оплату",
            is_active=True,
        )
        invoice = Invoice.objects.create(
            user=self.user,
            title="Готовый документ",
            amount=Decimal("1000.00"),
            amount_verified=True,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            counterparty=counterparty,
            responsible=responsible,
            status=Invoice.STATUS_NEW,
            planned_payment_date=date(2026, 7, 10),
        )

        self.client.force_login(
            self.staff
        )

        response = self.client.post(
            reverse(
                "quick_update_invoice",
                args=[
                    invoice.id,
                ],
            ),
            {
                "status": Invoice.STATUS_APPROVED,
                "planned_payment_date": "2026-07-25",
                "next": "/invoices/",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.status,
            Invoice.STATUS_APPROVED,
        )
        self.assertEqual(
            invoice.planned_payment_date,
            date(2026, 7, 25),
        )
