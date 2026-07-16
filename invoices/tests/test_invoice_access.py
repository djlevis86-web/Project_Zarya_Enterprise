import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.models import Invoice


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="zarya-test-media-")


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class InvoiceAccessTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass12345",
        )

        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="pass12345",
        )

        self.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.owner_invoice = self._create_invoice(
            user=self.owner,
            title="OWNER-INVOICE-ACCESS-TEST",
            filename="owner-invoice.pdf",
        )

        self.foreign_invoice = self._create_invoice(
            user=self.other_user,
            title="FOREIGN-INVOICE-ACCESS-TEST",
            filename="foreign-invoice.pdf",
        )

    def _create_invoice(self, user, title, filename):
        return Invoice.objects.create(
            user=user,
            title=title,
            original_filename=filename,
            file=SimpleUploadedFile(
                filename,
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            amount=Decimal("1000.00"),
            status=Invoice.STATUS_APPROVED,
            amount_verified=True,
        )

    def test_invoice_list_requires_login(self):
        response = self.client.get(reverse("invoice_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_regular_user_sees_only_own_invoices_in_list(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OWNER-INVOICE-ACCESS-TEST")
        self.assertNotContains(response, "FOREIGN-INVOICE-ACCESS-TEST")

    def test_staff_user_sees_all_invoices_in_list(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OWNER-INVOICE-ACCESS-TEST")
        self.assertContains(response, "FOREIGN-INVOICE-ACCESS-TEST")

    def test_regular_user_can_open_own_invoice_detail(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("invoice_detail", args=[self.owner_invoice.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OWNER-INVOICE-ACCESS-TEST")

    def test_regular_user_gets_404_for_foreign_invoice_detail(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("invoice_detail", args=[self.foreign_invoice.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_user_can_open_foreign_invoice_detail(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("invoice_detail", args=[self.foreign_invoice.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FOREIGN-INVOICE-ACCESS-TEST")