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
from invoices.payment_registry_services import (
    add_invoice_to_payment_registry,
    get_or_create_draft_payment_registry,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-registry-workspace-v7-"
)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PaymentRegistryWorkspaceV7Tests(TestCase):
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
            username="registry-workspace-v7",
            email="registry-workspace-v7@example.invalid",
            password="StrongTestPassword-2026",
            is_staff=True,
            is_superuser=True,
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО РАБОЧЕЕ ПРОСТРАНСТВО V7",
            full_name="ООО РАБОЧЕЕ ПРОСТРАНСТВО V7",
            inn="7705999701",
            kpp="770501001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810900000000701",
            bik="044525225",
        )
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный рабочего пространства V7",
            is_active=True,
        )

    def _create_invoice(
        self,
        *,
        title: str,
        planned_payment_date=None,
    ) -> Invoice:
        if planned_payment_date is None:
            planned_payment_date = (
                timezone.localdate()
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
            planned_payment_date=planned_payment_date,
            counterparty=self.counterparty,
            vendor=self.counterparty.name,
            counterparty_match_status=(
                Invoice.COUNTERPARTY_MATCH_FOUND
            ),
        )

    def _add_to_draft_registry(
        self,
        invoice: Invoice,
    ) -> PaymentRegistryItem:
        registry, _created = (
            get_or_create_draft_payment_registry(
                self.staff_user
            )
        )
        item, errors, _warnings = (
            add_invoice_to_payment_registry(
                invoice,
                registry,
            )
        )

        self.assertEqual(
            errors,
            [],
        )
        self.assertIsNotNone(
            item
        )

        return item

    def test_default_workspace_renders_current_registry_only(
        self,
    ) -> None:
        invoice = self._create_invoice(
            title="WORKSPACE-V7-CURRENT-DEFAULT",
        )
        self._add_to_draft_registry(
            invoice
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["registry_workspace"],
            "current",
        )
        self.assertContains(
            response,
            '<section id="registry-current-workspace"',
        )
        self.assertNotContains(
            response,
            '<section id="registry-document-queue"',
        )

    def test_queue_workspace_renders_queue_only(
        self,
    ) -> None:
        self._create_invoice(
            title="WORKSPACE-V7-QUEUE",
        )
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "queue",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["registry_workspace"],
            "queue",
        )
        self.assertContains(
            response,
            '<section id="registry-document-queue"',
        )
        self.assertNotContains(
            response,
            '<section id="registry-current-workspace"',
        )

    def test_invalid_workspace_falls_back_to_current(
        self,
    ) -> None:
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "invalid",
            },
        )

        self.assertEqual(
            response.context["registry_workspace"],
            "current",
        )
        self.assertContains(
            response,
            'aria-current="page"',
        )

    def test_current_registry_has_independent_pagination(
        self,
    ) -> None:
        for index in range(18):
            invoice = self._create_invoice(
                title=(
                    "WORKSPACE-V7-PAGINATION-"
                    f"{index + 1:02d}"
                ),
            )
            self._add_to_draft_registry(
                invoice
            )

        self.client.force_login(
            self.staff_user
        )

        first_page = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "current",
                "registry_page": "1",
            },
        )
        second_page = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "current",
                "registry_page": "2",
            },
        )

        self.assertEqual(
            first_page.context[
                "registry_page_obj"
            ].paginator.per_page,
            15,
        )
        self.assertEqual(
            first_page.context[
                "registry_page_obj"
            ].paginator.num_pages,
            2,
        )
        self.assertEqual(
            len(
                first_page.context[
                    "draft_registry_items"
                ]
            ),
            15,
        )
        self.assertEqual(
            len(
                second_page.context[
                    "draft_registry_items"
                ]
            ),
            3,
        )
        self.assertContains(
            first_page,
            "Страница 1 из 2",
        )
        self.assertContains(
            second_page,
            "Страница 2 из 2",
        )

    def test_queue_filter_form_preserves_workspace(
        self,
    ) -> None:
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "queue",
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
            },
        )

        self.assertContains(
            response,
            (
                '<input type="hidden" '
                'name="workspace" value="queue">'
            ),
        )
        self.assertContains(
            response,
            (
                "?workspace=queue"
                "#registry-document-queue"
            ),
        )

    def test_single_add_preserves_queue_workspace(
        self,
    ) -> None:
        invoice = self._create_invoice(
            title="WORKSPACE-V7-RETURN-QUEUE",
        )
        return_query = urlencode(
            [
                ("workspace", "queue"),
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

    def test_workspace_tabs_keep_queue_filter_context(
        self,
    ) -> None:
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "queue",
                "q": "молоко",
                "status": Invoice.STATUS_APPROVED,
                "page": "3",
            },
        )

        queue_query = response.context[
            "registry_queue_workspace_query"
        ]
        current_query = response.context[
            "registry_current_workspace_query"
        ]

        self.assertIn(
            "workspace=queue",
            queue_query,
        )
        self.assertIn(
            "q=%D0%BC%D0%BE%D0%BB%D0%BE%D0%BA%D0%BE",
            queue_query,
        )
        self.assertIn(
            "page=3",
            queue_query,
        )
        self.assertIn(
            "workspace=current",
            current_query,
        )
        self.assertNotIn(
            "page=3",
            current_query,
        )

    def test_queue_workspace_uses_visual_page_size(
        self,
    ) -> None:
        for index in range(17):
            self._create_invoice(
                title=(
                    "WORKSPACE-V13-QUEUE-PAGE-"
                    f"{index + 1:02d}"
                ),
            )

        self.client.force_login(
            self.staff_user
        )

        first_page = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "queue",
                "page": "1",
            },
        )
        second_page = self.client.get(
            reverse("payment_registry"),
            data={
                "workspace": "queue",
                "page": "2",
            },
        )

        self.assertEqual(
            first_page.context[
                "page_obj"
            ].paginator.per_page,
            15,
        )
        self.assertEqual(
            first_page.context[
                "page_obj"
            ].paginator.num_pages,
            2,
        )
        self.assertEqual(
            len(
                first_page.context[
                    "invoices"
                ]
            ),
            15,
        )
        self.assertEqual(
            len(
                second_page.context[
                    "invoices"
                ]
            ),
            2,
        )

    def test_registry_kpi_copy_separates_workspaces(
        self,
    ) -> None:
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry")
        )

        self.assertContains(
            response,
            "В текущем реестре",
        )
        self.assertContains(
            response,
            "Готовы к выгрузке",
        )
        self.assertContains(
            response,
            "Блокировки в реестре",
        )
        self.assertContains(
            response,
            "На странице очереди:",
        )

    def test_history_uses_finance_topbar_title(
        self,
    ) -> None:
        self.client.force_login(
            self.staff_user
        )

        response = self.client.get(
            reverse("payment_registry_history")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "История реестров",
            count=2,
        )
