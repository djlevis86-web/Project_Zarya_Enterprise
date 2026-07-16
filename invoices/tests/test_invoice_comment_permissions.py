from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from invoices.comment_models import InvoiceComment
from invoices.models import Invoice


class InvoiceCommentPermissionTests(TestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.temp_dir.name
        )
        self.override.enable()

        User = get_user_model()

        self.owner = User.objects.create_user(
            username="comment-owner",
            email="comment-owner@example.com",
            password="pass12345",
        )

        self.other_user = User.objects.create_user(
            username="comment-other",
            email="comment-other@example.com",
            password="pass12345",
        )

        self.staff_user = User.objects.create_user(
            username="comment-staff",
            email="comment-staff@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.owner,
            title="Comment permission invoice",
            amount=Decimal("1000.00"),
            status=Invoice.STATUS_NEW,
            file=SimpleUploadedFile(
                "comment-permission.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
        )

        self.url = reverse(
            "add_comment",
            kwargs={
                "invoice_id": self.invoice.id,
            },
        )

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()

    def test_owner_can_add_comment(self):
        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            self.url,
            {
                "text": "Комментарий владельца",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "invoice_detail",
                kwargs={
                    "invoice_id": self.invoice.id,
                },
            ),
        )

        comment = InvoiceComment.objects.get(
            invoice=self.invoice
        )

        self.assertEqual(
            comment.user,
            self.owner,
        )
        self.assertEqual(
            comment.text,
            "Комментарий владельца",
        )

    def test_staff_can_add_comment_to_another_users_invoice(self):
        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            self.url,
            {
                "text": "Комментарий сотрудника",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertTrue(
            InvoiceComment.objects.filter(
                invoice=self.invoice,
                user=self.staff_user,
                text="Комментарий сотрудника",
            ).exists()
        )

    def test_other_user_cannot_add_comment(self):
        self.client.force_login(
            self.other_user
        )

        response = self.client.post(
            self.url,
            {
                "text": "Чужой комментарий",
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertFalse(
            InvoiceComment.objects.filter(
                invoice=self.invoice,
                user=self.other_user,
            ).exists()
        )

    def test_get_does_not_add_comment(self):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            405,
        )
        self.assertFalse(
            InvoiceComment.objects.filter(
                invoice=self.invoice
            ).exists()
        )

    def test_deleted_invoice_does_not_accept_comment(self):
        self.invoice.is_deleted = True
        self.invoice.save(
            update_fields=[
                "is_deleted",
                "updated_at",
            ]
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            self.url,
            {
                "text": "Комментарий к удалённому документу",
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )
        self.assertFalse(
            InvoiceComment.objects.filter(
                invoice=self.invoice
            ).exists()
        )

    def test_comment_post_requires_csrf(self):
        csrf_client = Client(
            enforce_csrf_checks=True
        )
        csrf_client.force_login(
            self.owner
        )

        response = csrf_client.post(
            self.url,
            {
                "text": "Комментарий без CSRF",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )
        self.assertFalse(
            InvoiceComment.objects.filter(
                invoice=self.invoice
            ).exists()
        )
