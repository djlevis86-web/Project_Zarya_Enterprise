from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from invoices.models import (
    Counterparty,
    Invoice,
    PaymentRegistryItem,
    ResponsiblePerson,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-registry-filter-test-media-"
)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PaymentRegistryFilterPersistenceV20Tests(TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        shutil.rmtree(
            _TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self) -> None:
        User = get_user_model()
        self.staff_user = User.objects.create_user(
            username="registry-filter-staff",
            email="registry-filter-staff@example.invalid",
            password="StrongTestPassword-2026",
            is_staff=True,
            is_superuser=True,
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО ФИЛЬТРЫ РЕЕСТРА",
            full_name="ООО ФИЛЬТРЫ РЕЕСТРА",
            inn="7705999001",
            kpp="770501001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810900000000991",
            bik="044525225",
        )
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный фильтров реестра",
            is_active=True,
        )

    def _create_invoice(
        self,
        *,
        title: str,
        ready: bool = True,
    ) -> Invoice:
        counterparty = (
            self.counterparty
            if ready
            else None
        )

        return Invoice.objects.create(
            user=self.staff_user,
            responsible=self.responsible,
            title=title,
            original_filename=f"{title}.pdf",
            file=SimpleUploadedFile(
                f"{title}.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            amount=Decimal("12500.00"),
            status=Invoice.STATUS_APPROVED,
            amount_verified=True,
            planned_payment_date=timezone.localdate(),
            counterparty=counterparty,
            vendor=(
                counterparty.name
                if counterparty is not None
                else ""
            ),
            counterparty_match_status=(
                Invoice.COUNTERPARTY_MATCH_FOUND
                if counterparty is not None
                else Invoice.COUNTERPARTY_MATCH_NOT_FOUND
            ),
        )

    def test_single_add_preserves_full_registry_filter_query(
        self,
    ) -> None:
        invoice = self._create_invoice(
            title="FILTER-PERSISTENCE-SINGLE",
        )
        return_query = urlencode(
            [
                ("q", "молоко север"),
                ("status", Invoice.STATUS_APPROVED),
                ("payment_status", "unpaid"),
                ("ocr_status", "done"),
                ("date_from", "2026-08-01"),
                ("date_to", "2026-08-31"),
                ("page", "3"),
            ]
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [
                    str(invoice.id),
                ],
                "return_query": return_query,
            },
        )

        self.assertRedirects(
            response,
            (
                reverse("payment_registry")
                + "?"
                + return_query
                + "#registry-document-queue"
            ),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            PaymentRegistryItem.objects.filter(
                invoice=invoice,
            ).exists()
        )

    def test_bulk_add_preserves_filter_query_and_adds_all(
        self,
    ) -> None:
        first = self._create_invoice(
            title="FILTER-PERSISTENCE-BULK-1",
        )
        second = self._create_invoice(
            title="FILTER-PERSISTENCE-BULK-2",
        )
        third = self._create_invoice(
            title="FILTER-PERSISTENCE-BULK-3",
        )
        return_query = urlencode(
            [
                ("status", Invoice.STATUS_APPROVED),
                ("date_from", "2026-08-05"),
                ("date_to", "2026-08-05"),
                ("page", "1"),
            ]
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [
                    str(first.id),
                    str(second.id),
                    str(third.id),
                ],
                "return_query": return_query,
            },
        )

        self.assertRedirects(
            response,
            (
                reverse("payment_registry")
                + "?"
                + return_query
                + "#registry-document-queue"
            ),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            PaymentRegistryItem.objects.filter(
                invoice__in=[
                    first,
                    second,
                    third,
                ],
            ).count(),
            3,
        )

    def test_empty_selection_preserves_registry_filter_query(
        self,
    ) -> None:
        return_query = urlencode(
            [
                ("status", Invoice.STATUS_APPROVED),
                ("date_from", "2026-08-01"),
                ("date_to", "2026-08-31"),
                ("page", "2"),
            ]
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "return_query": return_query,
            },
        )

        self.assertRedirects(
            response,
            (
                reverse("payment_registry")
                + "?"
                + return_query
                + "#registry-document-queue"
            ),
            fetch_redirect_response=False,
        )

    def test_return_query_drops_unknown_and_duplicate_keys(
        self,
    ) -> None:
        invoice = self._create_invoice(
            title="FILTER-PERSISTENCE-SAFE-QUERY",
        )
        unsafe_query = (
            "status=approved"
            "&page=2"
            "&next=https%3A%2F%2Fevil.example"
            "&status=paid"
            "&unknown=value"
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.post(
            reverse("add_to_payment_registry"),
            data={
                "invoice_ids": [
                    str(invoice.id),
                ],
                "return_query": unsafe_query,
            },
        )

        self.assertRedirects(
            response,
            (
                reverse("payment_registry")
                + "?status=approved&page=2"
                + "#registry-document-queue"
            ),
            fetch_redirect_response=False,
        )

    def test_registry_page_renders_bulk_action_for_ready_rows(
        self,
    ) -> None:
        first = self._create_invoice(
            title="FILTER-BULK-RENDER-READY-1",
        )
        second = self._create_invoice(
            title="FILTER-BULK-RENDER-READY-2",
        )
        blocked = self._create_invoice(
            title="FILTER-BULK-RENDER-BLOCKED",
            ready=False,
        )
        today = timezone.localdate().isoformat()
        query = {
            "workspace": "queue",
            "status": Invoice.STATUS_APPROVED,
            "date_from": today,
            "date_to": today,
            "page": "1",
        }
        expected_query = urlencode(
            list(query.items())
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry"),
            data=query,
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["ready_page_count"],
            2,
        )
        self.assertEqual(
            response.context["registry_return_query"],
            expected_query,
        )
        self.assertContains(
            response,
            'id="registry-document-queue"',
        )
        self.assertContains(
            response,
            'id="registry-bulk-add-form"',
        )
        self.assertContains(
            response,
            "Добавить готовые · 2",
        )

        html = response.content.decode(
            "utf-8"
        )
        bulk_fragment = html.split(
            'id="registry-bulk-add-form"',
            1,
        )[1].split(
            "</form>",
            1,
        )[0]

        self.assertIn(
            f'value="{first.id}"',
            bulk_fragment,
        )
        self.assertIn(
            f'value="{second.id}"',
            bulk_fragment,
        )
        self.assertNotIn(
            f'value="{blocked.id}"',
            bulk_fragment,
        )
