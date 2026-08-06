import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.comment_models import InvoiceComment
from invoices.models import (
    Counterparty,
    Invoice,
    PaymentRegistry,
    PaymentRegistryItem,
    ResponsiblePerson,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-access-mutation-media-"
)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class UserAccessMutationPolicyTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(
            _TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username="mutation-manager",
            email="mutation-manager@example.com",
            password="pass12345",
            role=User.Role.MANAGER,
            is_staff=True,
        )
        self.general_director = User.objects.create_user(
            username="mutation-general-director",
            email="mutation-general-director@example.com",
            password="pass12345",
            role=User.Role.GENERAL_DIRECTOR,
            is_staff=False,
            is_superuser=False,
        )
        self.analyst = User.objects.create_user(
            username="mutation-analyst",
            email="mutation-analyst@example.com",
            password="pass12345",
            role=User.Role.ANALYST,
            is_staff=False,
            is_superuser=False,
        )
        self.uploader = User.objects.create_user(
            username="mutation-uploader",
            email="mutation-uploader@example.com",
            password="pass12345",
            role=User.Role.USER,
            is_staff=False,
        )
        self.other_uploader = User.objects.create_user(
            username="mutation-other-uploader",
            email="mutation-other-uploader@example.com",
            password="pass12345",
            role=User.Role.USER,
            is_staff=False,
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный по правам",
            is_active=True,
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО Права доступа",
            inn="3525001001",
            bank_name="Тестовый банк",
            account_number="40702810000000000001",
            bik="044705615",
            source=Counterparty.SOURCE_1C,
        )

        self.own_new = self._create_invoice(
            self.uploader,
            "OWNER NEW",
            Invoice.STATUS_NEW,
            amount_verified=True,
        )
        self.own_in_work = self._create_invoice(
            self.uploader,
            "OWNER IN WORK",
            Invoice.STATUS_IN_WORK,
            amount_verified=True,
        )
        self.own_on_approval = self._create_invoice(
            self.uploader,
            "OWNER ON APPROVAL",
            Invoice.STATUS_ON_APPROVAL,
            amount_verified=True,
        )
        self.own_approved = self._create_invoice(
            self.uploader,
            "OWNER APPROVED",
            Invoice.STATUS_APPROVED,
            amount_verified=True,
        )
        self.own_paid = self._create_invoice(
            self.uploader,
            "OWNER PAID",
            Invoice.STATUS_PAID,
            amount_verified=True,
        )
        self.foreign_new = self._create_invoice(
            self.other_uploader,
            "FOREIGN NEW",
            Invoice.STATUS_NEW,
            amount_verified=True,
        )
        self.active_registry_invoice = self._create_invoice(
            self.uploader,
            "OWNER ACTIVE REGISTRY",
            Invoice.STATUS_IN_WORK,
            amount_verified=True,
        )

        self.registry = PaymentRegistry.objects.create(
            title="Активный реестр блокировки",
            status=PaymentRegistry.STATUS_DRAFT,
            created_by=self.manager,
        )
        PaymentRegistryItem.objects.create(
            registry=self.registry,
            invoice=self.active_registry_invoice,
            amount=self.active_registry_invoice.amount,
            planned_payment_date=(
                self.active_registry_invoice.planned_payment_date
            ),
            status=PaymentRegistryItem.STATUS_ADDED,
        )

    def _create_invoice(
        self,
        user,
        title,
        status,
        *,
        amount_verified,
    ):
        filename = (
            title.lower()
            .replace(" ", "-")
            + ".pdf"
        )

        return Invoice.objects.create(
            user=user,
            title=title,
            description="Исходное описание",
            original_filename=filename,
            file=SimpleUploadedFile(
                filename,
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            vendor="ООО Права доступа",
            invoice_number="INV-ACCESS-1",
            invoice_date="06.08.2026",
            document_date=date(2026, 8, 6),
            amount=Decimal("1000.00"),
            ocr_amount=Decimal("1000.00"),
            amount_verified=amount_verified,
            ocr_verified=amount_verified,
            counterparty=self.counterparty,
            responsible=self.responsible,
            planned_payment_date=date(2026, 8, 15),
            payment_priority=3,
            status=status,
        )

    def _owner_payload(self, invoice, **overrides):
        payload = {
            "document_type": invoice.document_type,
            "title": invoice.title,
            "description": invoice.description or "",
            "vendor": invoice.vendor or "",
            "invoice_number": invoice.invoice_number or "",
            "invoice_date": invoice.invoice_date or "",
            "document_date": invoice.document_date.isoformat(),
            "amount": str(invoice.amount),
            "planned_payment_date": (
                invoice.planned_payment_date.isoformat()
            ),
            "responsible": str(
                invoice.responsible_id
            ),
        }
        payload.update(overrides)
        return payload

    def test_uploader_can_open_own_editable_documents(self):
        self.client.force_login(self.uploader)

        for invoice in (
            self.own_new,
            self.own_in_work,
            self.own_on_approval,
        ):
            with self.subTest(status=invoice.status):
                response = self.client.get(
                    reverse(
                        "edit_invoice",
                        args=[invoice.id],
                    )
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )
                self.assertTrue(
                    response.context["owner_edit_mode"]
                )

    def test_uploader_cannot_edit_foreign_locked_or_registry_document(self):
        self.client.force_login(self.uploader)

        for invoice in (
            self.foreign_new,
            self.own_approved,
            self.own_paid,
            self.active_registry_invoice,
        ):
            with self.subTest(
                invoice=invoice.title,
            ):
                response = self.client.get(
                    reverse(
                        "edit_invoice",
                        args=[invoice.id],
                    )
                )
                self.assertEqual(
                    response.status_code,
                    403,
                )

    def test_uploader_edit_ignores_finance_fields_and_unverifies_amount(self):
        self.client.force_login(self.uploader)

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[self.own_new.id],
            ),
            self._owner_payload(
                self.own_new,
                title="OWNER UPDATED",
                amount="1250.00",
                status=Invoice.STATUS_PAID,
                payment_priority="5",
                paid_at="2026-08-06",
                confirm_amount="1",
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.own_new.refresh_from_db()

        self.assertEqual(
            self.own_new.title,
            "OWNER UPDATED",
        )
        self.assertEqual(
            self.own_new.amount,
            Decimal("1250.00"),
        )
        self.assertEqual(
            self.own_new.status,
            Invoice.STATUS_NEW,
        )
        self.assertEqual(
            self.own_new.payment_priority,
            3,
        )
        self.assertIsNone(
            self.own_new.paid_at
        )
        self.assertFalse(
            self.own_new.amount_verified
        )
        self.assertFalse(
            self.own_new.ocr_verified
        )
        self.assertIn(
            "Требуется проверка финансовым директором",
            self.own_new.ocr_comment,
        )

    def test_uploader_cannot_post_edit_for_active_registry_document(self):
        self.client.force_login(self.uploader)
        original_title = self.active_registry_invoice.title

        response = self.client.post(
            reverse(
                "edit_invoice",
                args=[self.active_registry_invoice.id],
            ),
            self._owner_payload(
                self.active_registry_invoice,
                title="MUST NOT CHANGE",
            ),
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.active_registry_invoice.refresh_from_db()
        self.assertEqual(
            self.active_registry_invoice.title,
            original_title,
        )

    def test_general_director_can_approve_only_on_approval_document(self):
        self.client.force_login(
            self.general_director
        )

        response = self.client.post(
            reverse(
                "approve_invoice",
                args=[self.own_on_approval.id],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.own_on_approval.refresh_from_db()
        self.assertEqual(
            self.own_on_approval.status,
            Invoice.STATUS_APPROVED,
        )

        response = self.client.post(
            reverse(
                "approve_invoice",
                args=[self.own_new.id],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.own_new.refresh_from_db()
        self.assertEqual(
            self.own_new.status,
            Invoice.STATUS_NEW,
        )

    def test_general_director_cannot_use_other_invoice_mutations(self):
        self.client.force_login(
            self.general_director
        )

        cases = (
            (
                reverse(
                    "change_invoice_status",
                    args=[
                        self.own_new.id,
                        Invoice.STATUS_APPROVED,
                    ],
                ),
                {},
            ),
            (
                reverse(
                    "add_comment",
                    args=[self.own_new.id],
                ),
                {
                    "text": "Запрещённый комментарий",
                },
            ),
            (
                reverse(
                    "edit_invoice",
                    args=[self.own_new.id],
                ),
                self._owner_payload(
                    self.own_new,
                    title="GENERAL DIRECTOR EDIT",
                ),
            ),
            (
                reverse(
                    "add_to_payment_registry"
                ),
                {
                    "invoice_ids": [
                        str(self.own_approved.id),
                    ],
                },
            ),
        )

        for url, payload in cases:
            with self.subTest(url=url):
                response = self.client.post(
                    url,
                    payload,
                )
                self.assertEqual(
                    response.status_code,
                    403,
                )

        self.assertFalse(
            InvoiceComment.objects.filter(
                user=self.general_director,
            ).exists()
        )

    def test_analyst_cannot_mutate_any_invoice_surface(self):
        self.client.force_login(
            self.analyst
        )

        cases = (
            (
                reverse(
                    "approve_invoice",
                    args=[self.own_on_approval.id],
                ),
                {},
            ),
            (
                reverse(
                    "add_comment",
                    args=[self.own_new.id],
                ),
                {
                    "text": "Запрещённый комментарий",
                },
            ),
            (
                reverse(
                    "edit_invoice",
                    args=[self.own_new.id],
                ),
                self._owner_payload(
                    self.own_new,
                    title="ANALYST EDIT",
                ),
            ),
            (
                reverse(
                    "add_to_payment_registry"
                ),
                {
                    "invoice_ids": [
                        str(self.own_approved.id),
                    ],
                },
            ),
        )

        for url, payload in cases:
            with self.subTest(url=url):
                response = self.client.post(
                    url,
                    payload,
                )
                self.assertEqual(
                    response.status_code,
                    403,
                )

        self.assertFalse(
            InvoiceComment.objects.filter(
                user=self.analyst,
            ).exists()
        )

    def test_detail_actions_match_roles(self):
        self.client.force_login(
            self.general_director
        )

        response = self.client.get(
            reverse(
                "invoice_detail",
                args=[self.own_on_approval.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "Утвердить к оплате",
        )
        self.assertNotContains(
            response,
            "Редактировать",
        )
        self.assertNotContains(
            response,
            "Добавить рабочий комментарий",
        )

        self.client.force_login(
            self.analyst
        )

        response = self.client.get(
            reverse(
                "invoice_detail",
                args=[self.own_on_approval.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertNotContains(
            response,
            "Утвердить к оплате",
        )
        self.assertNotContains(
            response,
            "Редактировать",
        )
        self.assertNotContains(
            response,
            "Добавить рабочий комментарий",
        )

    def test_uploader_can_still_comment_on_own_document(self):
        self.client.force_login(
            self.uploader
        )

        response = self.client.post(
            reverse(
                "add_comment",
                args=[self.own_new.id],
            ),
            {
                "text": "Комментарий загрузчика",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertTrue(
            InvoiceComment.objects.filter(
                invoice=self.own_new,
                user=self.uploader,
                text="Комментарий загрузчика",
            ).exists()
        )
