from decimal import Decimal
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.approval_service import auto_approve_invoice
from invoices.models import Invoice


class InvoiceStatusWorkflowTests(TestCase):

    def test_status_choices_include_new_workflow(self):
        choices = dict(
            Invoice.STATUS_CHOICES
        )

        self.assertEqual(
            choices[Invoice.STATUS_NEW],
            "Новый",
        )
        self.assertEqual(
            choices[Invoice.STATUS_IN_WORK],
            "В работе",
        )
        self.assertEqual(
            choices[Invoice.STATUS_ON_APPROVAL],
            "На согласовании",
        )
        self.assertEqual(
            choices[Invoice.STATUS_APPROVED],
            "Утверждён",
        )
        self.assertEqual(
            choices[Invoice.STATUS_PAID],
            "Оплачен",
        )
        self.assertEqual(
            choices[Invoice.STATUS_REJECTED],
            "Отклонён",
        )

    def test_legacy_review_constant_points_to_in_work(self):
        self.assertEqual(
            Invoice.STATUS_REVIEW,
            Invoice.STATUS_IN_WORK,
        )

    def test_auto_approval_routes_medium_amount_to_in_work(self):
        invoice = SimpleNamespace(
            amount=Decimal("10000.00"),
            status=Invoice.STATUS_NEW,
        )

        status, message = auto_approve_invoice(
            invoice
        )

        self.assertEqual(
            status,
            Invoice.STATUS_IN_WORK,
        )
        self.assertEqual(
            invoice.status,
            Invoice.STATUS_IN_WORK,
        )
        self.assertIn(
            "менеджера",
            message,
        )

    def test_auto_approval_routes_large_amount_to_on_approval(self):
        invoice = SimpleNamespace(
            amount=Decimal("100000.00"),
            status=Invoice.STATUS_NEW,
        )

        status, message = auto_approve_invoice(
            invoice
        )

        self.assertEqual(
            status,
            Invoice.STATUS_ON_APPROVAL,
        )
        self.assertEqual(
            invoice.status,
            Invoice.STATUS_ON_APPROVAL,
        )
        self.assertIn(
            "согласование",
            message,
        )

    def test_auto_approval_routes_small_amount_to_approved(self):
        invoice = SimpleNamespace(
            amount=Decimal("1000.00"),
            status=Invoice.STATUS_NEW,
        )

        status, message = auto_approve_invoice(
            invoice
        )

        self.assertEqual(
            status,
            Invoice.STATUS_APPROVED,
        )
        self.assertEqual(
            invoice.status,
            Invoice.STATUS_APPROVED,
        )


class InvoiceStatusChangeViewTests(TestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.temp_dir.name
        )
        self.override.enable()

        User = get_user_model()

        self.staff_user = User.objects.create_user(
            username="status-staff",
            email="status-staff@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.staff_user,
            title="Status workflow invoice",
            amount=Decimal("1000.00"),
            status=Invoice.STATUS_NEW,
            file=SimpleUploadedFile(
                "status-workflow.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
        )

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()

    def test_staff_can_change_status_to_in_work(self):
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse(
                "change_invoice_status",
                kwargs={
                    "invoice_id": self.invoice.id,
                    "status": Invoice.STATUS_IN_WORK,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.STATUS_IN_WORK,
        )

    def test_staff_can_change_status_to_on_approval(self):
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse(
                "change_invoice_status",
                kwargs={
                    "invoice_id": self.invoice.id,
                    "status": Invoice.STATUS_ON_APPROVAL,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.STATUS_ON_APPROVAL,
        )
