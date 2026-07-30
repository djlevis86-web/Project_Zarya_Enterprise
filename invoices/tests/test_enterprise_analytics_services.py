from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from invoices.audit_models import InvoiceLog
from invoices.enterprise_analytics_services import (
    build_enterprise_dashboard_analytics,
    build_enterprise_payment_schedule_analytics,
    build_enterprise_registry_analytics,
    build_enterprise_upload_journal_analytics,
    enterprise_analytics_to_primitive,
)
from invoices.models import (
    Counterparty,
    Invoice,
    InvoicePayment,
    InvoiceUploadBatch,
    PaymentRegistry,
    PaymentRegistryItem,
    ResponsiblePerson,
)


User = get_user_model()


class EnterpriseAnalyticsServiceTests(TestCase):
    def setUp(self):
        self.today = date(
            2026,
            7,
            30,
        )

        self.user = User.objects.create_user(
            username="enterprise-user",
            email="enterprise@example.com",
            password="StrongPass123!",
            is_staff=True,
        )

        self.other_user = User.objects.create_user(
            username="other-user",
            email="other@example.com",
            password="StrongPass123!",
        )

        self.counterparty = (
            Counterparty.objects.create(
                name="Госкомплект ООО",
                inn="3525447980",
                bank_name="Банк",
                account_number="40702810",
                bik="044525225",
            )
        )

        self.responsible = (
            ResponsiblePerson.objects.create(
                full_name="Смолина Елена",
            )
        )

        self.other_responsible = (
            ResponsiblePerson.objects.create(
                full_name="Другой ответственный",
            )
        )

    def create_invoice(
        self,
        *,
        number: str,
        amount: str,
        planned_date: date | None,
        status: str = Invoice.STATUS_APPROVED,
        counterparty: Counterparty | None = None,
        responsible: ResponsiblePerson | None = None,
        amount_verified: bool = True,
        user=None,
    ) -> Invoice:
        return Invoice.objects.create(
            user=user or self.user,
            document_type=(
                Invoice.DOCUMENT_TYPE_INVOICE
            ),
            title=f"Счёт {number}",
            file=f"invoices/{number}.pdf",
            original_filename=f"{number}.pdf",
            amount=Decimal(amount),
            amount_verified=amount_verified,
            invoice_number=number,
            document_date=self.today,
            counterparty=(
                counterparty
                if counterparty is not None
                else self.counterparty
            ),
            responsible=(
                responsible
                if responsible is not None
                else self.responsible
            ),
            planned_payment_date=planned_date,
            status=status,
        )

    def build_dataset(self):
        due_today = self.create_invoice(
            number="TODAY",
            amount="100.00",
            planned_date=self.today,
        )

        InvoicePayment.objects.create(
            invoice=due_today,
            amount=Decimal("20.00"),
            paid_at=self.today,
            created_by=self.user,
        )

        overdue = self.create_invoice(
            number="OVERDUE",
            amount="200.00",
            planned_date=(
                self.today
                - timedelta(days=1)
            ),
        )

        blocked = self.create_invoice(
            number="BLOCKED",
            amount="300.00",
            planned_date=(
                self.today
                + timedelta(days=1)
            ),
            counterparty=None,
            responsible=None,
            amount_verified=False,
        )

        future = self.create_invoice(
            number="FUTURE",
            amount="400.00",
            planned_date=(
                self.today
                + timedelta(days=2)
            ),
        )

        paid = self.create_invoice(
            number="PAID",
            amount="500.00",
            planned_date=(
                self.today
                - timedelta(days=3)
            ),
            status=Invoice.STATUS_PAID,
        )

        InvoicePayment.objects.create(
            invoice=paid,
            amount=Decimal("500.00"),
            paid_at=self.today,
            created_by=self.user,
        )

        return {
            "due_today": due_today,
            "overdue": overdue,
            "blocked": blocked,
            "future": future,
            "paid": paid,
        }

    def test_dashboard_metrics_include_counts_and_remaining_amounts(self):
        self.build_dataset()

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
            )
        )

        metrics = {
            metric.code: metric
            for metric in analytics.metrics
        }

        self.assertEqual(
            metrics["needs_review"].count,
            1,
        )
        self.assertEqual(
            metrics["needs_review"].amount,
            Decimal("300.00"),
        )
        self.assertEqual(
            metrics["due_today"].count,
            1,
        )
        self.assertEqual(
            metrics["due_today"].amount,
            Decimal("80.00"),
        )
        self.assertEqual(
            metrics["overdue"].count,
            1,
        )
        self.assertEqual(
            metrics["overdue"].amount,
            Decimal("200.00"),
        )
        self.assertEqual(
            metrics["ready"].count,
            2,
        )
        self.assertEqual(
            metrics["ready"].amount,
            Decimal("480.00"),
        )

    def test_status_distribution_contains_count_amount_and_share(self):
        self.build_dataset()

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
            )
        )

        distribution = {
            item.code: item
            for item in (
                analytics.status_distribution
            )
        }

        approved = distribution[
            Invoice.STATUS_APPROVED
        ]

        paid = distribution[
            Invoice.STATUS_PAID
        ]

        self.assertEqual(
            approved.count,
            4,
        )
        self.assertEqual(
            approved.document_amount,
            Decimal("1000.00"),
        )
        self.assertEqual(
            approved.outstanding_amount,
            Decimal("980.00"),
        )
        self.assertEqual(
            approved.share_percent,
            Decimal("80.0"),
        )
        self.assertEqual(
            paid.count,
            1,
        )
        self.assertEqual(
            paid.outstanding_amount,
            Decimal("0.00"),
        )

    def test_payment_series_is_stable_and_includes_zero_days(self):
        self.build_dataset()

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
                series_days=4,
            )
        )

        self.assertEqual(
            len(analytics.payment_series),
            4,
        )
        self.assertEqual(
            analytics.payment_series[0].amount,
            Decimal("80.00"),
        )
        self.assertEqual(
            analytics.payment_series[1].amount,
            Decimal("300.00"),
        )
        self.assertEqual(
            analytics.payment_series[2].amount,
            Decimal("400.00"),
        )
        self.assertEqual(
            analytics.payment_series[3].amount,
            Decimal("0.00"),
        )

    def test_tasks_are_sorted_by_urgency(self):
        data = self.build_dataset()

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
                task_limit=10,
            )
        )

        task_ids = [
            task.invoice_id
            for task in analytics.tasks
        ]

        self.assertEqual(
            task_ids[:2],
            [
                data["blocked"].id,
                data["overdue"].id,
            ],
        )

    def test_task_queue_supports_explicit_responsible_scope(self):
        matching = self.create_invoice(
            number="MATCHING",
            amount="100.00",
            planned_date=self.today,
            amount_verified=False,
            responsible=self.responsible,
        )

        self.create_invoice(
            number="OTHER",
            amount="100.00",
            planned_date=self.today,
            amount_verified=False,
            responsible=self.other_responsible,
        )

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
                task_responsible_id=(
                    self.responsible.id
                ),
            )
        )

        self.assertEqual(
            analytics.task_scope,
            "responsible",
        )
        self.assertEqual(
            [
                task.invoice_id
                for task in analytics.tasks
            ],
            [matching.id],
        )

    def test_recent_actions_respect_visible_queryset_and_humanize_text(self):
        visible = self.create_invoice(
            number="VISIBLE",
            amount="100.00",
            planned_date=self.today,
        )

        hidden = self.create_invoice(
            number="HIDDEN",
            amount="100.00",
            planned_date=self.today,
            user=self.other_user,
        )

        InvoiceLog.objects.create(
            invoice=visible,
            user=self.user,
            action=(
                "OCR повторно выполнен массово"
            ),
        )

        InvoiceLog.objects.create(
            invoice=hidden,
            user=self.other_user,
            action="Скрытое действие",
        )

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.filter(
                    id=visible.id
                ),
                today=self.today,
            )
        )

        self.assertEqual(
            len(analytics.recent_actions),
            1,
        )
        self.assertEqual(
            analytics.recent_actions[0].invoice_id,
            visible.id,
        )
        self.assertEqual(
            analytics.recent_actions[0].action,
            "Повторная проверка данных выполнена",
        )

    def test_dashboard_analytics_uses_two_queries(self):
        invoice = self.create_invoice(
            number="QUERY",
            amount="100.00",
            planned_date=self.today,
        )

        InvoiceLog.objects.create(
            invoice=invoice,
            user=self.user,
            action="Документ загружен",
        )

        with self.assertNumQueries(2):
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
            )

    def test_payment_schedule_metrics_use_outstanding_balance(self):
        self.build_dataset()

        analytics = (
            build_enterprise_payment_schedule_analytics(
                Invoice.objects.all(),
                today=self.today,
                period_days=7,
            )
        )

        metrics = {
            metric.code: metric
            for metric in analytics.metrics
        }

        self.assertEqual(
            metrics["total"].count,
            4,
        )
        self.assertEqual(
            metrics["total"].amount,
            Decimal("980.00"),
        )
        self.assertEqual(
            metrics["today"].amount,
            Decimal("80.00"),
        )
        self.assertEqual(
            metrics["week"].amount,
            Decimal("780.00"),
        )
        self.assertEqual(
            metrics["overdue"].amount,
            Decimal("200.00"),
        )

    def test_largest_payments_are_limited_to_period_and_sorted(self):
        self.build_dataset()

        analytics = (
            build_enterprise_payment_schedule_analytics(
                Invoice.objects.all(),
                today=self.today,
                period_days=3,
                largest_payment_limit=2,
            )
        )

        self.assertEqual(
            [
                item.remaining_amount
                for item in analytics.largest_payments
            ],
            [
                Decimal("400.00"),
                Decimal("300.00"),
            ],
        )

    def test_upload_journal_analytics_aggregates_batch_counters(self):
        InvoiceUploadBatch.objects.create(
            user=self.user,
            total_files=10,
            uploaded_count=8,
            duplicate_count=1,
            skipped_count=1,
            status=(
                InvoiceUploadBatch
                .STATUS_PARTIAL
            ),
        )

        InvoiceUploadBatch.objects.create(
            user=self.user,
            total_files=5,
            uploaded_count=5,
            duplicate_count=0,
            skipped_count=0,
            status=(
                InvoiceUploadBatch
                .STATUS_COMPLETED
            ),
        )

        InvoiceUploadBatch.objects.create(
            user=self.user,
            total_files=2,
            uploaded_count=0,
            duplicate_count=2,
            skipped_count=0,
            status=(
                InvoiceUploadBatch
                .STATUS_EMPTY
            ),
        )

        with self.assertNumQueries(1):
            analytics = (
                build_enterprise_upload_journal_analytics(
                    InvoiceUploadBatch.objects.all()
                )
            )

        self.assertEqual(
            analytics.total_batches,
            3,
        )
        self.assertEqual(
            analytics.total_files,
            17,
        )
        self.assertEqual(
            analytics.uploaded_files,
            13,
        )
        self.assertEqual(
            analytics.duplicate_files,
            3,
        )
        self.assertEqual(
            analytics.skipped_files,
            1,
        )
        self.assertEqual(
            analytics.success_rate,
            Decimal("76.5"),
        )

    def test_registry_analytics_uses_canonical_check_result(self):
        first = self.create_invoice(
            number="REG-1",
            amount="100.00",
            planned_date=self.today,
        )

        second = self.create_invoice(
            number="REG-2",
            amount="200.00",
            planned_date=self.today,
        )

        registry = PaymentRegistry.objects.create(
            title="Реестр",
            status=(
                PaymentRegistry.STATUS_CHECKED
            ),
            created_by=self.user,
            items_count=2,
            total_amount=Decimal("300.00"),
        )

        PaymentRegistryItem.objects.create(
            registry=registry,
            invoice=first,
            amount=Decimal("100.00"),
            planned_payment_date=self.today,
        )

        PaymentRegistryItem.objects.create(
            registry=registry,
            invoice=second,
            amount=Decimal("200.00"),
            planned_payment_date=self.today,
        )

        check_result = {
            "items_count": 2,
            "ready_count": 1,
            "errors_count": 1,
            "warnings_count": 0,
            "errors": [
                {
                    "invoice_id": second.id,
                    "messages": [
                        "Не заполнены реквизиты",
                    ],
                }
            ],
            "warnings": [],
        }

        with self.assertNumQueries(1):
            analytics = (
                build_enterprise_registry_analytics(
                    registry,
                    items=(
                        registry.items
                        .select_related(
                            "invoice",
                            "invoice__counterparty",
                        )
                        .all()
                    ),
                    check_result=check_result,
                )
            )

        self.assertTrue(
            analytics.check_available
        )
        self.assertEqual(
            analytics.ready_count,
            1,
        )
        self.assertEqual(
            analytics.blocked_count,
            1,
        )
        self.assertEqual(
            analytics.calculated_total_amount,
            Decimal("300.00"),
        )
        self.assertTrue(
            analytics.is_total_amount_consistent
        )
        self.assertTrue(
            analytics.lifecycle[0].is_complete
        )
        self.assertTrue(
            analytics.lifecycle[1].is_current
        )
        self.assertEqual(
            analytics.issues[0].invoice_id,
            second.id,
        )

    def test_registry_without_check_result_does_not_claim_readiness(self):
        registry = PaymentRegistry.objects.create(
            title="Непроверенный реестр",
            created_by=self.user,
        )

        analytics = (
            build_enterprise_registry_analytics(
                registry,
                items=(),
            )
        )

        self.assertFalse(
            analytics.check_available
        )
        self.assertEqual(
            analytics.ready_count,
            0,
        )
        self.assertEqual(
            analytics.blocked_count,
            0,
        )

    def test_analytics_can_be_serialized_for_template_and_chart_payloads(self):
        self.build_dataset()

        analytics = (
            build_enterprise_dashboard_analytics(
                Invoice.objects.all(),
                today=self.today,
            )
        )

        payload = (
            enterprise_analytics_to_primitive(
                analytics
            )
        )

        self.assertIsInstance(
            payload,
            dict,
        )
        self.assertEqual(
            payload["payment_series"][0]["day"],
            "2026-07-30",
        )
        self.assertEqual(
            payload["metrics"][1]["amount"],
            "80.00",
        )
