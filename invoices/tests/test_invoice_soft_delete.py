from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import (
    Invoice,
    InvoicePayment,
    PaymentRegistry,
    PaymentRegistryItem,
)


class InvoiceSoftDeleteTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.staff = User.objects.create_user(
            username='invoice-delete-staff',
            email='invoice-delete-staff@example.com',
            password='pass',
            is_staff=True,
        )

        self.regular = User.objects.create_user(
            username='invoice-delete-user',
            email='invoice-delete-user@example.com',
            password='pass',
            is_staff=False,
        )

        self.invoice = Invoice.objects.create(
            user=self.regular,
            title='Счёт для удаления',
            amount=Decimal('1000.00'),
            status=Invoice.STATUS_NEW,
        )

    def test_staff_can_soft_delete_invoice(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                'delete_invoice',
                args=[
                    self.invoice.id,
                ],
            )
        )

        self.assertRedirects(
            response,
            reverse('invoice_list'),
        )

        self.invoice.refresh_from_db()

        self.assertTrue(
            self.invoice.is_deleted,
        )
        self.assertIsNotNone(
            self.invoice.deleted_at,
        )
        self.assertEqual(
            self.invoice.deleted_by,
            self.staff,
        )

    def test_deleted_invoice_is_hidden_from_list(self):
        self.invoice.is_deleted = True
        self.invoice.deleted_by = self.staff
        self.invoice.save(
            update_fields=[
                'is_deleted',
                'deleted_by',
                'updated_at',
            ]
        )

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('invoice_list')
        )

        self.assertNotContains(
            response,
            'Счёт для удаления',
        )

    def test_deleted_invoice_detail_returns_404(self):
        self.invoice.is_deleted = True
        self.invoice.deleted_by = self.staff
        self.invoice.save(
            update_fields=[
                'is_deleted',
                'deleted_by',
                'updated_at',
            ]
        )

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse(
                'invoice_detail',
                args=[
                    self.invoice.id,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_regular_user_cannot_delete_invoice(self):
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse(
                'delete_invoice',
                args=[
                    self.invoice.id,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.invoice.refresh_from_db()

        self.assertFalse(
            self.invoice.is_deleted,
        )

    def test_staff_cannot_delete_invoice_with_posted_payment(self):
        InvoicePayment.objects.create(
            invoice=self.invoice,
            amount=Decimal('100.00'),
            status=InvoicePayment.STATUS_POSTED,
            created_by=self.staff,
        )

        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                'delete_invoice',
                args=[
                    self.invoice.id,
                ],
            )
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

        self.assertFalse(
            self.invoice.is_deleted,
        )

    def test_staff_cannot_delete_invoice_in_active_payment_registry(self):
        registry = PaymentRegistry.objects.create(
            title='Реестр с удаляемым счётом',
            created_by=self.staff,
            status=PaymentRegistry.STATUS_DRAFT,
        )

        PaymentRegistryItem.objects.create(
            registry=registry,
            invoice=self.invoice,
            amount=self.invoice.amount,
            status=PaymentRegistryItem.STATUS_ADDED,
        )

        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                'delete_invoice',
                args=[
                    self.invoice.id,
                ],
            )
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

        self.assertFalse(
            self.invoice.is_deleted,
        )

