import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from invoices.models import Invoice, ResponsiblePerson


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-test-responsible-workflow-"
)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class ResponsibleInvoiceWorkflowTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        shutil.rmtree(
            _TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self):
        User = get_user_model()

        self.staff_user = User.objects.create_user(
            username="responsible-workflow-staff",
            email="responsible-workflow@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.active_responsible = ResponsiblePerson.objects.create(
            full_name="Активный Ответственный",
            is_active=True,
        )

        self.current_inactive_responsible = (
            ResponsiblePerson.objects.create(
                full_name="Текущий Неактивный Ответственный",
                is_active=False,
            )
        )

        self.other_inactive_responsible = (
            ResponsiblePerson.objects.create(
                full_name="Другой Неактивный Ответственный",
                is_active=False,
            )
        )

    def _create_invoice(
        self,
        responsible=None,
        title="RESPONSIBLE WORKFLOW INVOICE",
    ):
        return Invoice.objects.create(
            user=self.staff_user,
            responsible=responsible,
            title=title,
            original_filename=f"{title}.pdf",
            file=SimpleUploadedFile(
                f"{title}.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            amount=Decimal("1000.00"),
            amount_verified=True,
            planned_payment_date=timezone.localdate(),
            payment_priority=3,
            status=Invoice.STATUS_APPROVED,
        )

    def _edit_payload(self, responsible_id):
        return {
            "document_type": Invoice.DOCUMENT_TYPE_INVOICE,
            "title": "RESPONSIBLE WORKFLOW UPDATED",
            "description": "",
            "vendor": "",
            "invoice_number": "",
            "invoice_date": "",
            "document_date": "",
            "amount": "1000.00",
            "planned_payment_date": "2026-07-30",
            "responsible": (
                str(responsible_id)
                if responsible_id is not None
                else ""
            ),
            "payment_priority": "3",
            "paid_at": "",
            "status": Invoice.STATUS_APPROVED,
        }

    def test_invoice_detail_displays_responsible_name(self):
        invoice = self._create_invoice(
            responsible=self.active_responsible,
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse(
                "invoice_detail",
                args=[
                    invoice.id,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Ответственный",
        )

        self.assertContains(
            response,
            self.active_responsible.full_name,
        )

    def test_invoice_detail_displays_not_assigned_for_old_invoice(self):
        invoice = self._create_invoice(
            responsible=None,
            title="OLD INVOICE WITHOUT RESPONSIBLE",
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse(
                "invoice_detail",
                args=[
                    invoice.id,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Не назначен",
        )

    def test_staff_can_assign_active_responsible_through_edit_view(self):
        invoice = self._create_invoice(
            responsible=None,
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            ),
            self._edit_payload(
                self.active_responsible.id
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.responsible,
            self.active_responsible,
        )

    def test_current_inactive_responsible_remains_available(self):
        invoice = self._create_invoice(
            responsible=self.current_inactive_responsible,
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        responsible_ids = list(
            response.context["form"]
            .fields["responsible"]
            .queryset
            .values_list(
                "id",
                flat=True,
            )
        )

        self.assertIn(
            self.active_responsible.id,
            responsible_ids,
        )

        self.assertIn(
            self.current_inactive_responsible.id,
            responsible_ids,
        )

        self.assertNotIn(
            self.other_inactive_responsible.id,
            responsible_ids,
        )

    def test_tampered_inactive_responsible_is_rejected(self):
        invoice = self._create_invoice(
            responsible=self.active_responsible,
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            ),
            self._edit_payload(
                self.other_inactive_responsible.id
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "responsible",
            response.context["form"].errors,
        )

        invoice.refresh_from_db()

        self.assertEqual(
            invoice.responsible,
            self.active_responsible,
        )

    def test_edit_requires_responsible(self):
        invoice = self._create_invoice(
            responsible=None,
        )

        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[
                    invoice.id,
                ],
            ),
            self._edit_payload(
                None
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "responsible",
            response.context["form"].errors,
        )

        invoice.refresh_from_db()

        self.assertIsNone(
            invoice.responsible
        )
