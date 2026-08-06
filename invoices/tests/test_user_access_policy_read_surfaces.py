import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.models import Counterparty, Invoice, InvoiceUploadBatch, PaymentRegistry
from invoices.payment_registry_permissions import (
    user_can_cancel_payment_registry,
    user_can_check_payment_registry,
    user_can_export_payment_registry,
    user_can_manage_payment_registry,
    user_can_mark_payment_registry_paid,
)
from invoices.selectors import get_visible_invoices_for_user
from users.permissions import (
    user_can_approve_invoices,
    user_can_process_invoices,
    user_can_upload_invoices,
    user_can_view_all_invoices,
    user_can_view_finance_workspace,
)

_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="zarya-access-read-")


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class UserAccessPolicyReadSurfaceTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pass12345",
            role=User.Role.MANAGER, is_staff=True,
        )
        self.general = User.objects.create_user(
            username="general", email="general@example.com", password="pass12345",
            role=User.Role.GENERAL_DIRECTOR, is_staff=False, is_superuser=False,
        )
        self.analyst = User.objects.create_user(
            username="viewer", email="viewer@example.com", password="pass12345",
            role=User.Role.ANALYST, is_staff=False, is_superuser=False,
        )
        self.uploader = User.objects.create_user(
            username="uploader", email="uploader@example.com", password="pass12345",
            role=User.Role.USER,
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="pass12345",
            role=User.Role.USER,
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО Контрагент", source=Counterparty.SOURCE_MANUAL,
        )
        self.own_invoice = self._invoice(self.uploader, "OWN-INVOICE", "own.pdf")
        self.foreign_invoice = self._invoice(self.other, "FOREIGN-INVOICE", "foreign.pdf")
        self.foreign_batch = InvoiceUploadBatch.objects.create(
            user=self.other, total_files=1, uploaded_count=1,
            status=InvoiceUploadBatch.STATUS_COMPLETED,
        )
        self.registry = PaymentRegistry.objects.create(
            title="READ-REGISTRY", created_by=self.manager,
            status=PaymentRegistry.STATUS_DRAFT,
        )

    def _invoice(self, user, title, filename):
        return Invoice.objects.create(
            user=user, title=title, original_filename=filename,
            file=SimpleUploadedFile(filename, b"%PDF-1.4\n%EOF", content_type="application/pdf"),
            amount=Decimal("1000.00"), amount_verified=True,
            status=Invoice.STATUS_ON_APPROVAL, counterparty=self.counterparty,
        )

    def test_role_labels(self):
        User = get_user_model()
        labels = dict(User.Role.choices)
        self.assertEqual(labels[User.Role.GENERAL_DIRECTOR], "Генеральный директор")
        self.assertEqual(labels[User.Role.ANALYST], "Полный просмотр")

    def test_general_director_matrix(self):
        self.assertTrue(user_can_view_finance_workspace(self.general))
        self.assertTrue(user_can_view_all_invoices(self.general))
        self.assertTrue(user_can_approve_invoices(self.general))
        self.assertTrue(user_can_export_payment_registry(self.general))
        self.assertFalse(user_can_process_invoices(self.general))
        self.assertFalse(user_can_upload_invoices(self.general))
        self.assertFalse(user_can_manage_payment_registry(self.general))
        self.assertFalse(user_can_check_payment_registry(self.general))
        self.assertFalse(user_can_mark_payment_registry_paid(self.general))
        self.assertFalse(user_can_cancel_payment_registry(self.general))

    def test_analyst_matrix(self):
        self.assertTrue(user_can_view_finance_workspace(self.analyst))
        self.assertTrue(user_can_view_all_invoices(self.analyst))
        self.assertTrue(user_can_export_payment_registry(self.analyst))
        self.assertFalse(user_can_approve_invoices(self.analyst))
        self.assertFalse(user_can_process_invoices(self.analyst))
        self.assertFalse(user_can_upload_invoices(self.analyst))
        self.assertFalse(user_can_manage_payment_registry(self.analyst))

    def test_visibility_selector(self):
        expected = {self.own_invoice.id, self.foreign_invoice.id}
        for user in (self.general, self.analyst):
            self.assertEqual(
                set(get_visible_invoices_for_user(user).values_list("id", flat=True)),
                expected,
            )
        self.assertEqual(
            set(get_visible_invoices_for_user(self.uploader).values_list("id", flat=True)),
            {self.own_invoice.id},
        )

    def test_read_roles_open_finance_surfaces(self):
        urls = (
            reverse("invoice_list"), reverse("payment_schedule"),
            reverse("payment_registry"), reverse("payment_registry_history"),
            reverse("payment_registry_detail", args=[self.registry.id]),
            reverse("upload_batches"),
            reverse("upload_batch_detail", args=[self.foreign_batch.id]),
            reverse("counterparty_directory"),
            reverse("counterparty_detail", args=[self.counterparty.id]),
        )
        for user in (self.general, self.analyst):
            self.client.force_login(user)
            for url in urls:
                with self.subTest(role=user.role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_read_roles_see_all_documents_and_not_upload(self):
        for user in (self.general, self.analyst):
            self.client.force_login(user)
            response = self.client.get(reverse("invoice_list"))
            self.assertContains(response, "OWN-INVOICE")
            self.assertContains(response, "FOREIGN-INVOICE")
            self.assertContains(response, "График платежей")
            self.assertContains(response, "Реестр оплаты")
            self.assertContains(response, "Контрагенты")
            self.assertEqual(self.client.get(reverse("upload_invoice")).status_code, 403)
