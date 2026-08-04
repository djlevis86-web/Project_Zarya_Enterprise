from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.models import (
    Counterparty,
    Invoice,
    InvoicePayment,
    ResponsiblePerson,
)


class PaymentSurfacesV20ViewTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="payment-surfaces-v20",
            email="payment-surfaces-v20@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )

        self.counterparty = Counterparty.objects.create(
            name="ООО ПЛАТЁЖНЫЙ КОНТРАГЕНТ",
            full_name="ООО ПЛАТЁЖНЫЙ КОНТРАГЕНТ",
            inn="7705551199",
            kpp="770501099",
            bank_name="АО БАНК V20",
            account_number="40702810900000000099",
            bik="044525299",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный V20",
            is_active=True,
        )

        self.today = timezone.localdate()
        self.client.force_login(self.user)

    def _invoice(
        self,
        *,
        title,
        amount=Decimal("100.00"),
        planned_payment_date=None,
        status=Invoice.STATUS_APPROVED,
    ):
        return Invoice.objects.create(
            user=self.user,
            responsible=self.responsible,
            title=title,
            original_filename=f"{title}.pdf",
            file=f"invoices/{title}.pdf",
            amount=amount,
            ocr_amount=amount,
            amount_verified=True,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            invoice_number=title,
            document_date=self.today,
            invoice_date=self.today.strftime("%d.%m.%Y"),
            vendor=self.counterparty.name,
            counterparty=self.counterparty,
            counterparty_match_status=Invoice.COUNTERPARTY_MATCH_FOUND,
            planned_payment_date=(
                planned_payment_date
                if planned_payment_date is not None
                else self.today + timedelta(days=1)
            ),
            status=status,
        )

    def _payment(
        self,
        invoice,
        amount,
    ):
        return InvoicePayment.objects.create(
            invoice=invoice,
            amount=amount,
            paid_at=self.today,
            status=InvoicePayment.STATUS_POSTED,
            source=InvoicePayment.SOURCE_MANUAL,
            created_by=self.user,
        )

    def test_schedule_uses_positive_outstanding_balance_everywhere(self):
        partial = self._invoice(
            title="V20-SCHEDULE-PARTIAL",
            amount=Decimal("100.00"),
        )
        self._payment(
            partial,
            Decimal("40.00"),
        )

        paid = self._invoice(
            title="V20-SCHEDULE-PAID",
            amount=Decimal("50.00"),
        )
        self._payment(
            paid,
            Decimal("50.00"),
        )

        response = self.client.get(
            reverse("payment_schedule"),
            {
                "filter": "week",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["total_count"],
            1,
        )
        self.assertEqual(
            response.context["filtered_count"],
            1,
        )
        self.assertEqual(
            response.context["total_amount"],
            Decimal("60.00"),
        )
        self.assertEqual(
            response.context["filtered_amount"],
            Decimal("60.00"),
        )
        self.assertEqual(
            response.context["page_obj"].paginator.count,
            1,
        )

        series_total = sum(
            (
                point.amount
                for point in (
                    response.context[
                        "schedule_analytics"
                    ].payment_series
                )
            ),
            Decimal("0.00"),
        )

        self.assertEqual(
            series_total,
            Decimal("60.00"),
        )

        largest = (
            response.context[
                "schedule_analytics"
            ].largest_payments
        )

        self.assertEqual(
            len(largest),
            1,
        )
        self.assertEqual(
            largest[0].remaining_amount,
            Decimal("60.00"),
        )

    def test_schedule_paginates_and_keeps_non_period_filters(self):
        for index in range(22):
            self._invoice(
                title=f"V20-SCHEDULE-PAGE-{index:02d}",
            )

        response = self.client.get(
            reverse("payment_schedule"),
            {
                "filter": "all",
                "q": "V20-SCHEDULE-PAGE",
                "status": Invoice.STATUS_APPROVED,
                "page": "2",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["filtered_count"],
            22,
        )
        self.assertEqual(
            response.context["page_obj"].paginator.count,
            22,
        )
        self.assertEqual(
            response.context["page_obj"].number,
            2,
        )
        self.assertEqual(
            len(response.context["invoices"]),
            2,
        )

        for tab in response.context[
            "schedule_period_links"
        ]:
            query_string = tab[
                "query_string"
            ]

            self.assertIn(
                "q=V20-SCHEDULE-PAGE",
                query_string,
            )
            self.assertIn(
                "status=approved",
                query_string,
            )
            self.assertNotIn(
                "page=",
                query_string,
            )

        self.assertNotIn(
            "page=",
            response.context[
                "pagination_query"
            ],
        )

    def test_registry_uses_remaining_balance_and_paginates_queue(self):
        for index in range(26):
            self._invoice(
                title=f"V20-REGISTRY-PAGE-{index:02d}",
            )

        partial = self._invoice(
            title="V20-REGISTRY-PARTIAL",
            amount=Decimal("100.00"),
        )
        self._payment(
            partial,
            Decimal("40.00"),
        )

        paid = self._invoice(
            title="V20-REGISTRY-PAID",
            amount=Decimal("100.00"),
        )
        self._payment(
            paid,
            Decimal("100.00"),
        )

        response = self.client.get(
            reverse("payment_registry"),
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["total_count"],
            27,
        )
        self.assertEqual(
            response.context["total_amount"],
            Decimal("2660.00"),
        )
        self.assertEqual(
            response.context["page_obj"].paginator.count,
            27,
        )
        self.assertEqual(
            len(response.context["invoices"]),
            25,
        )
        self.assertContains(
            response,
            "Показано 25 из 27",
        )

    def test_registry_pagination_keeps_filters(self):
        for index in range(27):
            self._invoice(
                title=f"V20-REGISTRY-FILTER-{index:02d}",
            )

        response = self.client.get(
            reverse("payment_registry"),
            {
                "q": "V20-REGISTRY-FILTER",
                "status": Invoice.STATUS_APPROVED,
                "page": "2",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["page_obj"].number,
            2,
        )
        self.assertIn(
            "q=V20-REGISTRY-FILTER",
            response.context[
                "pagination_query"
            ],
        )
        self.assertIn(
            "status=approved",
            response.context[
                "pagination_query"
            ],
        )
        self.assertNotIn(
            "page=",
            response.context[
                "pagination_query"
            ],
        )


class PaymentSurfacesV20StaticTests(TestCase):
    def test_templates_expose_pagination_and_selected_system_statuses(self):
        base = Path(settings.BASE_DIR)

        schedule = (
            base
            / "templates/invoices/payment_schedule.html"
        ).read_text(
            encoding="utf-8-sig"
        )
        registry = (
            base
            / "templates/invoices/payment_registry.html"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            'name="filter" value="{{ filter_type }}"',
            schedule,
        )
        self.assertIn(
            "enterprise-schedule-pagination",
            schedule,
        )
        self.assertIn(
            "selected_status == 'payment'",
            schedule,
        )
        self.assertIn(
            "selected_status == 'all'",
            schedule,
        )
        self.assertIn(
            "enterprise-registry-pagination",
            registry,
        )
        self.assertIn(
            "Показано {{ invoices|length }} из {{ total_count }}",
            registry,
        )

    def test_queryset_annotation_does_not_shadow_invoice_property(self):
        base = Path(settings.BASE_DIR)

        helper = (
            base
            / "invoices/view_modules/payment_registry_helpers.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "payment_outstanding_amount=ExpressionWrapper(",
            helper,
        )
        self.assertIn(
            "payment_outstanding_amount__gt=Decimal",
            helper,
        )
        self.assertNotIn(
            "payment_remaining_amount=ExpressionWrapper(",
            helper,
        )

    def test_v20_page_css_avoids_patch_techniques(self):
        base = Path(settings.BASE_DIR)

        for relative in (
            "static/css/pages/payment-schedule.css",
            "static/css/pages/payment-registry.css",
        ):
            css = (
                base
                / relative
            ).read_text(
                encoding="utf-8-sig"
            )

            with self.subTest(
                relative=relative
            ):
                self.assertNotIn(
                    "!important",
                    css,
                )
                self.assertNotIn(
                    "nth-child(",
                    css,
                )
                self.assertNotIn(
                    "rgba(",
                    css.lower(),
                )
