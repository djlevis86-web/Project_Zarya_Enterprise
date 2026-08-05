from __future__ import annotations

import hashlib
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from invoices.comment_models import InvoiceComment
from invoices.models import (
    Counterparty,
    Invoice,
    InvoiceFieldReview,
    InvoicePayment,
    InvoiceUploadBatch,
    OCRJob,
    PaymentRegistry,
    PaymentRegistryItem,
    ResponsiblePerson,
)


DEMO_PREFIX = "[DEMO-ZARYA:"
DEMO_EXTERNAL_PREFIX = "DEMO-ZARYA-"
DEMO_BATCH_PREFIX = "demo-zarya-"
EXPECTED_LOCAL_BASE_DIR = Path(r"D:\Project_Zarya")


@dataclass(frozen=True)
class ProfilePlan:
    counterparties: int
    responsible_people: int
    current_registry_items: int
    ready_queue: int
    blocked_queue: int
    workflow_documents: int
    history_registries: int
    history_items_per_registry: int

    @property
    def history_documents(self) -> int:
        return (
            self.history_registries
            * self.history_items_per_registry
        )

    @property
    def total_documents(self) -> int:
        return (
            self.current_registry_items
            + self.ready_queue
            + self.blocked_queue
            + self.workflow_documents
            + self.history_documents
        )


PROFILES: dict[str, ProfilePlan] = {
    "small": ProfilePlan(
        counterparties=16,
        responsible_people=4,
        current_registry_items=12,
        ready_queue=12,
        blocked_queue=6,
        workflow_documents=8,
        history_registries=2,
        history_items_per_registry=4,
    ),
    "visual": ProfilePlan(
        counterparties=72,
        responsible_people=8,
        current_registry_items=78,
        ready_queue=78,
        blocked_queue=24,
        workflow_documents=18,
        history_registries=5,
        history_items_per_registry=6,
    ),
    "stress": ProfilePlan(
        counterparties=240,
        responsible_people=16,
        current_registry_items=300,
        ready_queue=450,
        blocked_queue=180,
        workflow_documents=120,
        history_registries=12,
        history_items_per_registry=20,
    ),
}


class Command(BaseCommand):
    help = (
        "Create deterministic synthetic Project Zarya data for local "
        "visual and workflow testing."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--profile",
            choices=tuple(PROFILES),
            default="visual",
        )
        parser.add_argument(
            "--seed",
            default="20260805",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self._assert_local_safety()

        profile_name = str(options["profile"])
        seed_value = str(options["seed"])
        plan = PROFILES[profile_name]
        marker = self._marker(seed_value)

        if options["dry_run"]:
            self._print_plan(
                profile_name=profile_name,
                seed_value=seed_value,
                plan=plan,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "DEMO DATA DRY RUN: OK"
                )
            )
            return

        if options["reset"]:
            self._reset_all_demo_data()
            self.stdout.write(
                self.style.SUCCESS(
                    "DEMO DATA RESET: OK"
                )
            )
            return

        if options["validate_only"]:
            self._validate_seed(
                marker=marker,
                plan=plan,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "DEMO DATA VALIDATION: OK"
                )
            )
            return

        if options["replace"]:
            self._reset_all_demo_data()

        existing_count = Invoice.objects.filter(
            title__startswith=marker,
        ).count()

        if existing_count:
            raise CommandError(
                "Demo seed already exists. "
                "Use --replace or --reset."
            )

        rng = random.Random(seed_value)
        anchor_date = self._anchor_date(seed_value)
        created_storage_names: list[str] = []

        try:
            with transaction.atomic():
                result = self._create_demo_data(
                    profile_name=profile_name,
                    seed_value=seed_value,
                    marker=marker,
                    plan=plan,
                    rng=rng,
                    anchor_date=anchor_date,
                    created_storage_names=created_storage_names,
                )

                self._validate_seed(
                    marker=marker,
                    plan=plan,
                )
        except Exception:
            self._delete_storage_names(
                created_storage_names
            )
            raise

        self.stdout.write("")
        self.stdout.write(
            "=== PROJECT ZARYA DEMO DATA CREATED ==="
        )

        for key, value in result.items():
            self.stdout.write(
                f"{key}: {value}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "PROJECT ZARYA DEMO DATA SEED: OK"
            )
        )

    def _assert_local_safety(self) -> None:
        if os.environ.get("ALLOW_DEMO_SEED") != "1":
            raise CommandError(
                "ALLOW_DEMO_SEED=1 is required."
            )

        if not settings.DEBUG:
            raise CommandError(
                "Demo seeding is forbidden when DEBUG=False."
            )

        settings_module = os.environ.get(
            "DJANGO_SETTINGS_MODULE",
            "",
        ).lower()

        if "production" in settings_module:
            raise CommandError(
                "Demo seeding is forbidden with production settings."
            )

        if connection.vendor != "sqlite":
            raise CommandError(
                "Demo seeding is allowed only for local SQLite."
            )

        database_name = str(
            connection.settings_dict.get(
                "NAME",
                "",
            )
        )
        normalized_database = (
            database_name
            .replace("\\", "/")
            .lower()
        )
        is_test_database = (
            database_name == ":memory:"
            or normalized_database.startswith(
                "file:memorydb_"
            )
            or "mode=memory" in normalized_database
        )

        if not is_test_database:
            actual_base = os.path.normcase(
                str(
                    Path(settings.BASE_DIR).resolve()
                )
            )
            expected_base = os.path.normcase(
                str(
                    EXPECTED_LOCAL_BASE_DIR.resolve()
                )
            )

            if actual_base != expected_base:
                raise CommandError(
                    "Unexpected BASE_DIR. "
                    f"Expected {expected_base}; "
                    f"actual {actual_base}."
                )

            expected_database = os.path.normcase(
                str(
                    (
                        EXPECTED_LOCAL_BASE_DIR
                        / "db.sqlite3"
                    ).resolve()
                )
            )
            actual_database = os.path.normcase(
                str(
                    Path(database_name).resolve()
                )
            )

            if actual_database != expected_database:
                raise CommandError(
                    "Unexpected SQLite database. "
                    f"Expected {expected_database}; "
                    f"actual {actual_database}."
                )

    def _marker(self, seed_value: str) -> str:
        safe_seed = "".join(
            char
            for char in seed_value
            if char.isalnum() or char in "-_"
        )

        if not safe_seed:
            raise CommandError(
                "Seed must contain at least one safe character."
            )

        return f"{DEMO_PREFIX}{safe_seed}]"

    def _anchor_date(self, seed_value: str) -> date:
        if (
            len(seed_value) == 8
            and seed_value.isdigit()
        ):
            try:
                return datetime.strptime(
                    seed_value,
                    "%Y%m%d",
                ).date()
            except ValueError:
                pass

        digest = hashlib.sha256(
            seed_value.encode("utf-8")
        ).digest()
        offset = int.from_bytes(
            digest[:2],
            "big",
        ) % 365

        return date(2026, 1, 1) + timedelta(
            days=offset
        )

    def _aware_datetime(
        self,
        value_date: date,
        hour: int = 9,
        minute: int = 0,
    ) -> datetime:
        naive = datetime.combine(
            value_date,
            time(
                hour=hour,
                minute=minute,
            ),
        )

        return timezone.make_aware(
            naive,
            timezone.get_current_timezone(),
        )

    def _print_plan(
        self,
        *,
        profile_name: str,
        seed_value: str,
        plan: ProfilePlan,
    ) -> None:
        self.stdout.write(
            "=== PROJECT ZARYA DEMO DATA PLAN ==="
        )
        self.stdout.write(
            f"PROFILE: {profile_name}"
        )
        self.stdout.write(
            f"SEED: {seed_value}"
        )
        self.stdout.write(
            f"COUNTERPARTIES: {plan.counterparties}"
        )
        self.stdout.write(
            "RESPONSIBLE PEOPLE: "
            f"{plan.responsible_people}"
        )
        self.stdout.write(
            "CURRENT REGISTRY ITEMS: "
            f"{plan.current_registry_items}"
        )
        self.stdout.write(
            f"READY QUEUE: {plan.ready_queue}"
        )
        self.stdout.write(
            f"BLOCKED QUEUE: {plan.blocked_queue}"
        )
        self.stdout.write(
            "WORKFLOW DOCUMENTS: "
            f"{plan.workflow_documents}"
        )
        self.stdout.write(
            "HISTORY REGISTRIES: "
            f"{plan.history_registries}"
        )
        self.stdout.write(
            "HISTORY DOCUMENTS: "
            f"{plan.history_documents}"
        )
        self.stdout.write(
            f"TOTAL DOCUMENTS: {plan.total_documents}"
        )
        self.stdout.write(
            "DATABASE WRITES: NONE"
        )

    def _select_actor(self):
        User = get_user_model()

        actor = (
            User.objects.filter(
                is_active=True,
                is_superuser=True,
            )
            .order_by("pk")
            .first()
        )

        if actor is None:
            actor = (
                User.objects.filter(
                    is_active=True,
                    is_staff=True,
                )
                .order_by("pk")
                .first()
            )

        if actor is None:
            raise CommandError(
                "An active staff or superuser is required."
            )

        return actor

    def _create_demo_data(
        self,
        *,
        profile_name: str,
        seed_value: str,
        marker: str,
        plan: ProfilePlan,
        rng: random.Random,
        anchor_date: date,
        created_storage_names: list[str],
    ) -> dict[str, int | str]:
        actor = self._select_actor()
        counterparties = self._create_counterparties(
            marker=marker,
            plan=plan,
        )
        responsible_people = (
            self._create_responsible_people(
                marker=marker,
                plan=plan,
            )
        )
        batches = self._create_upload_batches(
            marker=marker,
            actor=actor,
            plan=plan,
            anchor_date=anchor_date,
        )

        ready_counterparties = [
            item
            for item in counterparties
            if (
                item.is_active
                and item.bank_name
                and item.bik
                and item.account_number
            )
        ]
        incomplete_counterparties = [
            item
            for item in counterparties
            if not (
                item.bank_name
                and item.bik
                and item.account_number
            )
        ]

        if not ready_counterparties:
            raise CommandError(
                "No ready synthetic counterparties were created."
            )

        active_responsible = [
            item
            for item in responsible_people
            if item.is_active
        ]

        if not active_responsible:
            raise CommandError(
                "No active responsible people were created."
            )

        document_counter = 0
        payment_counter = 0
        comment_counter = 0
        ocr_job_counter = 0
        history_registry_counter = 0

        history_statuses = (
            "checked",
            "exported",
            "partially_paid",
            "paid",
            "cancelled",
        )

        for history_index in range(
            plan.history_registries
        ):
            registry_status = history_statuses[
                history_index
                % len(history_statuses)
            ]
            registry_date = (
                anchor_date
                - timedelta(
                    days=35 + history_index * 11
                )
            )
            registry = PaymentRegistry.objects.create(
                title=(
                    f"{marker} Архивный реестр "
                    f"{history_index + 1:02d}"
                ),
                status=registry_status,
                created_by=actor,
                checked_by=(
                    actor
                    if registry_status
                    in {
                        "checked",
                        "exported",
                        "partially_paid",
                        "paid",
                    }
                    else None
                ),
                exported_by=(
                    actor
                    if registry_status
                    in {
                        "exported",
                        "partially_paid",
                        "paid",
                    }
                    else None
                ),
                checked_at=(
                    self._aware_datetime(
                        registry_date,
                        10,
                    )
                    if registry_status
                    in {
                        "checked",
                        "exported",
                        "partially_paid",
                        "paid",
                    }
                    else None
                ),
                exported_at=(
                    self._aware_datetime(
                        registry_date,
                        12,
                    )
                    if registry_status
                    in {
                        "exported",
                        "partially_paid",
                        "paid",
                    }
                    else None
                ),
                paid_at=(
                    self._aware_datetime(
                        registry_date,
                        15,
                    )
                    if registry_status == "paid"
                    else None
                ),
                items_count=0,
                total_amount=Decimal("0.00"),
                comment=(
                    f"{marker} Синтетический архивный "
                    "реестр для визуальной проверки."
                ),
            )
            PaymentRegistry.objects.filter(
                pk=registry.pk
            ).update(
                created_at=self._aware_datetime(
                    registry_date,
                    8,
                )
            )

            registry_total = Decimal("0.00")

            for item_index in range(
                plan.history_items_per_registry
            ):
                document_counter += 1
                amount = self._amount(
                    rng=rng,
                    index=document_counter,
                )
                invoice_status = (
                    "paid"
                    if registry_status == "paid"
                    else "approved"
                )
                invoice = self._make_invoice(
                    marker=marker,
                    seed_value=seed_value,
                    sequence=document_counter,
                    category="history",
                    status=invoice_status,
                    amount=amount,
                    document_date=(
                        registry_date
                        - timedelta(days=5 + item_index)
                    ),
                    planned_payment_date=registry_date,
                    paid_at=(
                        registry_date
                        if invoice_status == "paid"
                        else None
                    ),
                    counterparty=ready_counterparties[
                        document_counter
                        % len(ready_counterparties)
                    ],
                    responsible=active_responsible[
                        document_counter
                        % len(active_responsible)
                    ],
                    actor=actor,
                    upload_batch=batches[
                        document_counter
                        % len(batches)
                    ],
                    created_storage_names=(
                        created_storage_names
                    ),
                    amount_verified=True,
                    document_type=self._document_type(
                        document_counter
                    ),
                    rng=rng,
                )
                item_status = "added"

                if registry_status in {
                    "exported",
                    "partially_paid",
                }:
                    item_status = "exported"
                elif registry_status == "paid":
                    item_status = "paid"
                elif registry_status == "cancelled":
                    item_status = "cancelled"

                registry_item = (
                    PaymentRegistryItem.objects.create(
                        registry=registry,
                        invoice=invoice,
                        amount=amount,
                        planned_payment_date=(
                            registry_date
                        ),
                        status=item_status,
                        exported_at=(
                            self._aware_datetime(
                                registry_date,
                                12,
                            )
                            if item_status
                            in {
                                "exported",
                                "paid",
                            }
                            else None
                        ),
                        paid_at=(
                            self._aware_datetime(
                                registry_date,
                                15,
                            )
                            if item_status == "paid"
                            else None
                        ),
                        comment=(
                            f"{marker} Архивная позиция."
                        ),
                    )
                )
                registry_total += amount

                if registry_status == "paid":
                    self._create_payment(
                        invoice=invoice,
                        registry_item=registry_item,
                        actor=actor,
                        amount=amount,
                        paid_at=registry_date,
                        sequence=document_counter,
                    )
                    payment_counter += 1
                elif (
                    registry_status
                    == "partially_paid"
                    and item_index % 2 == 0
                ):
                    partial_amount = (
                        amount
                        * Decimal("0.40")
                    ).quantize(
                        Decimal("0.01")
                    )
                    self._create_payment(
                        invoice=invoice,
                        registry_item=registry_item,
                        actor=actor,
                        amount=partial_amount,
                        paid_at=registry_date,
                        sequence=document_counter,
                    )
                    payment_counter += 1

            PaymentRegistry.objects.filter(
                pk=registry.pk
            ).update(
                items_count=(
                    plan.history_items_per_registry
                ),
                total_amount=registry_total,
            )
            history_registry_counter += 1

        current_registry = PaymentRegistry.objects.create(
            title=(
                f"{marker} Текущий реестр — "
                f"{plan.current_registry_items} документов"
            ),
            status="draft",
            created_by=actor,
            checked_by=None,
            exported_by=None,
            checked_at=None,
            exported_at=None,
            paid_at=None,
            items_count=0,
            total_amount=Decimal("0.00"),
            comment=(
                f"{marker} Активный реестр для "
                "визуальной проверки."
            ),
        )
        PaymentRegistry.objects.filter(
            pk=current_registry.pk
        ).update(
            created_at=self._aware_datetime(
                anchor_date,
                8,
            )
        )

        current_total = Decimal("0.00")

        for item_index in range(
            plan.current_registry_items
        ):
            document_counter += 1
            amount = self._amount(
                rng=rng,
                index=document_counter,
            )
            planned_date = (
                anchor_date
                + timedelta(
                    days=item_index % 14
                )
            )
            invoice = self._make_invoice(
                marker=marker,
                seed_value=seed_value,
                sequence=document_counter,
                category="current_registry",
                status="approved",
                amount=amount,
                document_date=(
                    anchor_date
                    - timedelta(
                        days=item_index % 45
                    )
                ),
                planned_payment_date=planned_date,
                paid_at=None,
                counterparty=ready_counterparties[
                    item_index
                    % len(ready_counterparties)
                ],
                responsible=active_responsible[
                    item_index
                    % len(active_responsible)
                ],
                actor=actor,
                upload_batch=batches[
                    item_index
                    % len(batches)
                ],
                created_storage_names=(
                    created_storage_names
                ),
                amount_verified=True,
                document_type=self._document_type(
                    document_counter
                ),
                rng=rng,
            )
            PaymentRegistryItem.objects.create(
                registry=current_registry,
                invoice=invoice,
                amount=amount,
                planned_payment_date=planned_date,
                status="added",
                exported_at=None,
                paid_at=None,
                comment=(
                    f"{marker} Активная позиция "
                    f"{item_index + 1:03d}."
                ),
            )
            current_total += amount

        PaymentRegistry.objects.filter(
            pk=current_registry.pk
        ).update(
            items_count=plan.current_registry_items,
            total_amount=current_total,
        )

        for queue_index in range(
            plan.ready_queue
        ):
            document_counter += 1
            amount = self._amount(
                rng=rng,
                index=document_counter,
            )
            invoice = self._make_invoice(
                marker=marker,
                seed_value=seed_value,
                sequence=document_counter,
                category="ready_queue",
                status="approved",
                amount=amount,
                document_date=(
                    anchor_date
                    - timedelta(
                        days=queue_index % 35
                    )
                ),
                planned_payment_date=(
                    anchor_date
                    + timedelta(
                        days=(queue_index % 21) - 3
                    )
                ),
                paid_at=None,
                counterparty=ready_counterparties[
                    (queue_index + 7)
                    % len(ready_counterparties)
                ],
                responsible=active_responsible[
                    (queue_index + 2)
                    % len(active_responsible)
                ],
                actor=actor,
                upload_batch=batches[
                    queue_index
                    % len(batches)
                ],
                created_storage_names=(
                    created_storage_names
                ),
                amount_verified=True,
                document_type=self._document_type(
                    document_counter
                ),
                rng=rng,
            )

            if queue_index % 11 == 0:
                partial_amount = (
                    amount
                    * Decimal("0.25")
                ).quantize(
                    Decimal("0.01")
                )
                self._create_payment(
                    invoice=invoice,
                    registry_item=None,
                    actor=actor,
                    amount=partial_amount,
                    paid_at=anchor_date,
                    sequence=document_counter,
                )
                payment_counter += 1

        blocked_scenarios = (
            "missing_payment_date",
            "unverified_amount",
            "missing_counterparty",
            "missing_requisites",
            "missing_responsible",
            "zero_balance",
            "missing_ocr",
            "unknown_type",
        )

        for blocked_index in range(
            plan.blocked_queue
        ):
            document_counter += 1
            scenario = blocked_scenarios[
                blocked_index
                % len(blocked_scenarios)
            ]
            amount = self._amount(
                rng=rng,
                index=document_counter,
            )
            counterparty = ready_counterparties[
                blocked_index
                % len(ready_counterparties)
            ]
            responsible = active_responsible[
                blocked_index
                % len(active_responsible)
            ]
            planned_date = (
                anchor_date
                + timedelta(
                    days=blocked_index % 12
                )
            )
            amount_verified = True
            document_type = self._document_type(
                document_counter
            )

            if scenario == "missing_payment_date":
                planned_date = None
            elif scenario == "unverified_amount":
                amount_verified = False
            elif scenario == "missing_counterparty":
                counterparty = None
            elif scenario == "missing_requisites":
                if incomplete_counterparties:
                    counterparty = (
                        incomplete_counterparties[
                            blocked_index
                            % len(
                                incomplete_counterparties
                            )
                        ]
                    )
                else:
                    counterparty = None
            elif scenario == "missing_responsible":
                responsible = None
            elif scenario == "unknown_type":
                document_type = "unknown"
                amount_verified = False

            invoice = self._make_invoice(
                marker=marker,
                seed_value=seed_value,
                sequence=document_counter,
                category=(
                    "blocked:"
                    + scenario
                ),
                status="approved",
                amount=amount,
                document_date=(
                    anchor_date
                    - timedelta(
                        days=blocked_index % 20
                    )
                ),
                planned_payment_date=planned_date,
                paid_at=None,
                counterparty=counterparty,
                responsible=responsible,
                actor=actor,
                upload_batch=batches[
                    blocked_index
                    % len(batches)
                ],
                created_storage_names=(
                    created_storage_names
                ),
                amount_verified=amount_verified,
                document_type=document_type,
                rng=rng,
                blank_ocr=(
                    scenario == "missing_ocr"
                ),
            )

            if scenario == "zero_balance":
                self._create_payment(
                    invoice=invoice,
                    registry_item=None,
                    actor=actor,
                    amount=amount,
                    paid_at=anchor_date,
                    sequence=document_counter,
                )
                payment_counter += 1

            if scenario in {
                "missing_ocr",
                "unknown_type",
            }:
                ocr_status = (
                    "error"
                    if scenario == "missing_ocr"
                    else "pending"
                )
                self._create_ocr_job(
                    invoice=invoice,
                    actor=actor,
                    status=ocr_status,
                    sequence=document_counter,
                    anchor_date=anchor_date,
                    marker=marker,
                )
                ocr_job_counter += 1

        workflow_statuses = (
            "new",
            "in_work",
            "on_approval",
            "approved",
            "paid",
            "rejected",
        )

        for workflow_index in range(
            plan.workflow_documents
        ):
            document_counter += 1
            status = workflow_statuses[
                workflow_index
                % len(workflow_statuses)
            ]
            amount = self._amount(
                rng=rng,
                index=document_counter,
            )
            paid_at = (
                anchor_date
                if status == "paid"
                else None
            )
            invoice = self._make_invoice(
                marker=marker,
                seed_value=seed_value,
                sequence=document_counter,
                category=(
                    "workflow:"
                    + status
                ),
                status=status,
                amount=amount,
                document_date=(
                    anchor_date
                    - timedelta(
                        days=workflow_index % 30
                    )
                ),
                planned_payment_date=(
                    anchor_date
                    + timedelta(
                        days=workflow_index % 18
                    )
                ),
                paid_at=paid_at,
                counterparty=ready_counterparties[
                    workflow_index
                    % len(ready_counterparties)
                ],
                responsible=active_responsible[
                    workflow_index
                    % len(active_responsible)
                ],
                actor=actor,
                upload_batch=batches[
                    workflow_index
                    % len(batches)
                ],
                created_storage_names=(
                    created_storage_names
                ),
                amount_verified=(
                    status
                    not in {
                        "new",
                        "rejected",
                    }
                ),
                document_type=self._document_type(
                    document_counter
                ),
                rng=rng,
            )

            if status == "paid":
                self._create_payment(
                    invoice=invoice,
                    registry_item=None,
                    actor=actor,
                    amount=amount,
                    paid_at=anchor_date,
                    sequence=document_counter,
                )
                payment_counter += 1

            if workflow_index % 3 == 0:
                ocr_status = (
                    "processing"
                    if status
                    in {
                        "new",
                        "in_work",
                    }
                    else "done"
                )
                self._create_ocr_job(
                    invoice=invoice,
                    actor=actor,
                    status=ocr_status,
                    sequence=document_counter,
                    anchor_date=anchor_date,
                    marker=marker,
                )
                ocr_job_counter += 1

            if workflow_index % 2 == 0:
                InvoiceComment.objects.create(
                    invoice=invoice,
                    user=actor,
                    text=(
                        f"{marker} Демонстрационный "
                        "комментарий для проверки "
                        "переноса длинного текста."
                    ),
                )
                comment_counter += 1

        return {
            "PROFILE": profile_name,
            "SEED": seed_value,
            "ACTOR": actor.get_username(),
            "COUNTERPARTIES": len(counterparties),
            "RESPONSIBLE PEOPLE": (
                len(responsible_people)
            ),
            "UPLOAD BATCHES": len(batches),
            "DOCUMENTS": document_counter,
            "CURRENT REGISTRY ITEMS": (
                plan.current_registry_items
            ),
            "READY QUEUE DOCUMENTS": (
                plan.ready_queue
            ),
            "BLOCKED DOCUMENTS": (
                plan.blocked_queue
            ),
            "HISTORY REGISTRIES": (
                history_registry_counter
            ),
            "PAYMENTS": payment_counter,
            "OCR JOBS": ocr_job_counter,
            "COMMENTS": comment_counter,
        }

    def _create_counterparties(
        self,
        *,
        marker: str,
        plan: ProfilePlan,
    ) -> list[Counterparty]:
        legal_forms = (
            "ООО",
            "АО",
            "ИП",
            "СПК",
            "ПК",
        )
        roots = (
            "Северный агроснаб",
            "Вологодские молочные технологии",
            "Региональная топливная компания",
            "Агропромышленная логистика",
            "Технические системы фермы",
            "Комбикормовый союз",
            "Энергоресурс",
            "Ветеринарные решения",
            "Транспортная компания",
            "Сервис промышленного оборудования",
            "Лаборатория качества молока",
            "Строительно-монтажное управление",
        )
        result: list[Counterparty] = []

        for index in range(
            plan.counterparties
        ):
            legal_form = legal_forms[
                index % len(legal_forms)
            ]
            root = roots[
                index % len(roots)
            ]
            suffix = (
                "имени демонстрационного "
                "производственного участка"
                if index % 13 == 0
                else f"№ {index + 1:03d}"
            )
            name = (
                f"{legal_form} «{root} {suffix}»"
            )
            has_requisites = (
                index % 9 != 0
            )
            is_active = (
                index % 17 != 0
            )
            counterparty = Counterparty.objects.create(
                external_id_1c=(
                    f"{DEMO_EXTERNAL_PREFIX}"
                    f"{index + 1:05d}"
                ),
                name=name,
                full_name=(
                    f"{marker} Полное наименование: "
                    f"{name}"
                ),
                inn=f"77{index + 10000000:08d}"[-10:],
                kpp=f"35{index + 1000000:07d}"[-9:],
                bank_name=(
                    f"{marker} Демонстрационный банк"
                    if has_requisites
                    else ""
                ),
                bik=(
                    f"04{index + 1000000:07d}"[-9:]
                    if has_requisites
                    else ""
                ),
                account_number=(
                    f"40702810{index + 100000000000:012d}"[
                        -20:
                    ]
                    if has_requisites
                    else ""
                ),
                correspondent_account=(
                    f"30101810{index + 200000000000:012d}"[
                        -20:
                    ]
                    if has_requisites
                    else ""
                ),
                email=(
                    f"demo-{index + 1:03d}"
                    "@example.invalid"
                ),
                phone=(
                    f"+7 900 000-{index // 100:02d}-"
                    f"{index % 100:02d}"
                ),
                source="manual",
                is_active=is_active,
                synced_at=None,
                sync_comment=(
                    f"{marker} Synthetic local-only record."
                ),
            )
            result.append(
                counterparty
            )

        return result

    def _create_responsible_people(
        self,
        *,
        marker: str,
        plan: ProfilePlan,
    ) -> list[ResponsiblePerson]:
        names = (
            "Анна Сергеевна Воронова",
            "Михаил Андреевич Орлов",
            "Елена Викторовна Белова",
            "Павел Игоревич Смирнов",
            "Наталья Олеговна Крылова",
            "Дмитрий Романович Волков",
            "Ольга Петровна Соколова",
            "Алексей Николаевич Лебедев",
            "Марина Юрьевна Зимина",
            "Иван Аркадьевич Фролов",
            "Светлана Денисовна Морозова",
            "Роман Валерьевич Титов",
            "Ксения Максимовна Громова",
            "Вадим Константинович Егоров",
            "Людмила Степановна Ковалева",
            "Артём Борисович Серов",
        )
        result: list[ResponsiblePerson] = []

        for index in range(
            plan.responsible_people
        ):
            result.append(
                ResponsiblePerson.objects.create(
                    full_name=(
                        f"{marker} {names[index]}"
                    ),
                    is_active=(
                        index
                        != plan.responsible_people - 1
                        or plan.responsible_people <= 4
                    ),
                )
            )

        return result

    def _create_upload_batches(
        self,
        *,
        marker: str,
        actor: Any,
        plan: ProfilePlan,
        anchor_date: date,
    ) -> list[InvoiceUploadBatch]:
        total_batches = max(
            2,
            min(
                12,
                plan.total_documents // 35 + 1,
            ),
        )
        result: list[InvoiceUploadBatch] = []

        for index in range(total_batches):
            batch = InvoiceUploadBatch.objects.create(
                user=actor,
                upload_token=(
                    f"{DEMO_BATCH_PREFIX}"
                    f"{marker.replace('[', '').replace(']', '')}-"
                    f"{index + 1:02d}"
                ),
                total_files=25 + index * 3,
                uploaded_count=23 + index * 3,
                duplicate_count=index % 3,
                skipped_count=index % 2,
                duplicate_files=[
                    f"demo_duplicate_{index + 1}.pdf"
                ]
                if index % 3
                else [],
                skipped_files=[
                    f"demo_skipped_{index + 1}.pdf"
                ]
                if index % 2
                else [],
                status=(
                    "partial"
                    if index % 3 == 1
                    else "completed"
                ),
            )
            InvoiceUploadBatch.objects.filter(
                pk=batch.pk
            ).update(
                created_at=self._aware_datetime(
                    anchor_date
                    - timedelta(days=index * 4),
                    11,
                )
            )
            result.append(
                batch
            )

        return result

    def _amount(
        self,
        *,
        rng: random.Random,
        index: int,
    ) -> Decimal:
        bases = (
            Decimal("7420.00"),
            Decimal("15845.80"),
            Decimal("27420.00"),
            Decimal("56370.45"),
            Decimal("112500.00"),
            Decimal("248630.90"),
            Decimal("510800.00"),
            Decimal("1250000.00"),
        )
        base = bases[
            index % len(bases)
        ]
        variation = Decimal(
            str(
                rng.randint(
                    0,
                    900000,
                )
            )
        ) / Decimal("100")

        return (
            base + variation
        ).quantize(
            Decimal("0.01")
        )

    def _document_type(
        self,
        sequence: int,
    ) -> str:
        values = (
            "invoice",
            "invoice",
            "upd",
            "waybill",
            "payment_document",
        )

        return values[
            sequence % len(values)
        ]

    def _make_invoice(
        self,
        *,
        marker: str,
        seed_value: str,
        sequence: int,
        category: str,
        status: str,
        amount: Decimal,
        document_date: date,
        planned_payment_date: date | None,
        paid_at: date | None,
        counterparty: Counterparty | None,
        responsible: ResponsiblePerson | None,
        actor: Any,
        upload_batch: InvoiceUploadBatch,
        created_storage_names: list[str],
        amount_verified: bool,
        document_type: str,
        rng: random.Random,
        blank_ocr: bool = False,
    ) -> Invoice:
        document_number = (
            f"ДЕМО-{document_date:%Y%m%d}-"
            f"{sequence:05d}"
        )
        vendor = (
            counterparty.name
            if counterparty is not None
            else ""
        )
        original_filename = (
            f"DEMO_ZARYA_{seed_value}_"
            f"{sequence:05d}.pdf"
        )
        content = (
            "%PDF-1.4\n"
            f"% {marker}\n"
            f"% document {sequence}\n"
            "1 0 obj<</Type/Catalog>>endobj\n"
            "trailer<</Root 1 0 R>>\n"
            "%%EOF\n"
        ).encode("utf-8")
        file_hash = hashlib.sha256(
            content
        ).hexdigest()
        ocr_text = ""

        if not blank_ocr:
            ocr_text = (
                f"{marker}\n"
                f"Счёт № {document_number}\n"
                f"Поставщик: {vendor or 'не определён'}\n"
                f"Сумма: {amount:.2f}\n"
                "Синтетический документ. "
                "Не является платёжным основанием."
            )

        invoice = Invoice(
            user=actor,
            document_type=document_type,
            upload_batch=upload_batch,
            title=(
                f"{marker} {category} "
                f"№ {sequence:05d}"
            ),
            description=(
                f"{marker} Синтетический документ "
                "для локальной визуальной проверки."
            ),
            original_filename=original_filename,
            file_hash=file_hash,
            amount=amount,
            ocr_amount=amount,
            ocr_verified=(
                bool(ocr_text)
                and amount_verified
            ),
            ocr_comment=(
                f"{marker} deterministic OCR result"
            ),
            amount_verified=amount_verified,
            ocr_text=ocr_text,
            invoice_number=document_number,
            invoice_date=document_date.strftime(
                "%d.%m.%Y"
            ),
            document_date=document_date,
            vendor=vendor,
            counterparty=counterparty,
            counterparty_match_status=(
                "found"
                if counterparty is not None
                else "not_found"
            ),
            counterparty_match_comment=(
                f"{marker} Synthetic match."
            ),
            status=status,
            responsible=responsible,
            planned_payment_date=(
                planned_payment_date
            ),
            paid_at=paid_at,
            payment_priority=(
                sequence % 5 + 1
            ),
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
        )
        invoice.file.save(
            (
                f"demo_seed/{seed_value}/"
                f"{original_filename}"
            ),
            ContentFile(content),
            save=False,
        )
        created_storage_names.append(
            invoice.file.name
        )
        invoice.save()

        created_date = (
            document_date
            - timedelta(
                days=rng.randint(
                    0,
                    12,
                )
            )
        )
        Invoice.objects.filter(
            pk=invoice.pk
        ).update(
            created_at=self._aware_datetime(
                created_date,
                9,
                sequence % 60,
            ),
            updated_at=self._aware_datetime(
                document_date,
                16,
                sequence % 60,
            ),
        )

        review_values = {
            "amount": f"{amount:.2f}",
            "invoice_number": document_number,
            "document_date": (
                document_date.isoformat()
            ),
            "vendor": vendor,
        }

        for field_name, current_value in (
            review_values.items()
        ):
            is_confirmed = bool(
                current_value
            )

            if field_name == "amount":
                is_confirmed = (
                    is_confirmed
                    and amount_verified
                )

            InvoiceFieldReview.objects.update_or_create(
                invoice=invoice,
                field_name=field_name,
                defaults={
                    "recognized_value": (
                        current_value
                        if ocr_text
                        else ""
                    ),
                    "recognized_source": (
                        "ocr"
                        if ocr_text
                        else "unknown"
                    ),
                    "recognized_at": (
                        self._aware_datetime(
                            document_date,
                            10,
                        )
                        if ocr_text
                        else None
                    ),
                    "current_value": current_value,
                    "confirmed_value": (
                        current_value
                        if is_confirmed
                        else ""
                    ),
                    "is_confirmed": is_confirmed,
                    "confirmed_by": (
                        actor
                        if is_confirmed
                        else None
                    ),
                    "confirmed_at": (
                        self._aware_datetime(
                            document_date,
                            13,
                        )
                        if is_confirmed
                        else None
                    ),
                },
            )

        return invoice

    def _create_payment(
        self,
        *,
        invoice: Invoice,
        registry_item: PaymentRegistryItem | None,
        actor: Any,
        amount: Decimal,
        paid_at: date,
        sequence: int,
    ) -> InvoicePayment:
        return InvoicePayment.objects.create(
            invoice=invoice,
            registry_item=registry_item,
            status="posted",
            source=(
                "registry"
                if registry_item is not None
                else "manual"
            ),
            amount=amount,
            paid_at=paid_at,
            payment_number=(
                f"ДЕМО-ПП-{sequence:06d}"
            ),
            comment=(
                f"{DEMO_PREFIX} Синтетическая оплата."
            ),
            created_by=actor,
        )

    def _create_ocr_job(
        self,
        *,
        invoice: Invoice,
        actor: Any,
        status: str,
        sequence: int,
        anchor_date: date,
        marker: str,
    ) -> OCRJob:
        started_at = None
        finished_at = None

        if status in {
            "processing",
            "done",
            "error",
        }:
            started_at = self._aware_datetime(
                anchor_date,
                7,
                sequence % 60,
            )

        if status in {
            "done",
            "error",
        }:
            finished_at = self._aware_datetime(
                anchor_date,
                8,
                sequence % 60,
            )

        return OCRJob.objects.create(
            invoice=invoice,
            user=actor,
            status=status,
            source="upload",
            attempts=(
                2
                if status == "error"
                else 1
            ),
            message=(
                f"{marker} Synthetic OCR status."
            ),
            error_message=(
                f"{marker} Test OCR timeout."
                if status == "error"
                else ""
            ),
            started_at=started_at,
            finished_at=finished_at,
        )

    def _validate_seed(
        self,
        *,
        marker: str,
        plan: ProfilePlan,
    ) -> None:
        invoices = Invoice.objects.filter(
            title__startswith=marker,
        )
        registries = PaymentRegistry.objects.filter(
            title__startswith=marker,
        )
        current_registry = registries.filter(
            status="draft",
        ).order_by(
            "-created_at",
            "-pk",
        ).first()

        actual_documents = invoices.count()

        if actual_documents != plan.total_documents:
            raise CommandError(
                "Demo document count mismatch. "
                f"Expected {plan.total_documents}; "
                f"actual {actual_documents}."
            )

        expected_registries = (
            plan.history_registries + 1
        )
        actual_registries = registries.count()

        if actual_registries != expected_registries:
            raise CommandError(
                "Demo registry count mismatch. "
                f"Expected {expected_registries}; "
                f"actual {actual_registries}."
            )

        if current_registry is None:
            raise CommandError(
                "Current demo registry is absent."
            )

        actual_current_items = (
            current_registry.items.count()
        )

        if (
            actual_current_items
            != plan.current_registry_items
        ):
            raise CommandError(
                "Current registry item count mismatch. "
                f"Expected {plan.current_registry_items}; "
                f"actual {actual_current_items}."
            )

        expected_reviews = (
            plan.total_documents * 4
        )
        actual_reviews = (
            InvoiceFieldReview.objects.filter(
                invoice__title__startswith=marker,
            ).count()
        )

        if actual_reviews != expected_reviews:
            raise CommandError(
                "Field review count mismatch. "
                f"Expected {expected_reviews}; "
                f"actual {actual_reviews}."
            )

        missing_files = []

        for invoice in invoices.only(
            "file"
        ).iterator():
            if (
                not invoice.file
                or not invoice.file.storage.exists(
                    invoice.file.name
                )
            ):
                missing_files.append(
                    str(invoice.pk)
                )

                if len(missing_files) >= 5:
                    break

        if missing_files:
            raise CommandError(
                "Demo media files are missing for invoices: "
                + ", ".join(missing_files)
            )

        self.stdout.write(
            "DEMO DOCUMENTS: "
            f"{actual_documents}"
        )
        self.stdout.write(
            "DEMO REGISTRIES: "
            f"{actual_registries}"
        )
        self.stdout.write(
            "CURRENT REGISTRY ITEMS: "
            f"{actual_current_items}"
        )
        self.stdout.write(
            "FIELD REVIEWS: "
            f"{actual_reviews}"
        )
        self.stdout.write(
            "DEMO MEDIA FILES: PRESENT"
        )

    def _reset_all_demo_data(self) -> None:
        demo_invoices = Invoice.objects.filter(
            title__startswith=DEMO_PREFIX,
        )
        storage_pairs = [
            (
                invoice.file.storage,
                invoice.file.name,
            )
            for invoice in demo_invoices.only(
                "file"
            )
            if invoice.file
        ]
        invoice_count = demo_invoices.count()
        registry_count = (
            PaymentRegistry.objects.filter(
                title__startswith=DEMO_PREFIX,
            ).count()
        )
        counterparty_count = (
            Counterparty.objects.filter(
                external_id_1c__startswith=(
                    DEMO_EXTERNAL_PREFIX
                ),
            ).count()
        )
        responsible_count = (
            ResponsiblePerson.objects.filter(
                full_name__startswith=DEMO_PREFIX,
            ).count()
        )
        batch_count = (
            InvoiceUploadBatch.objects.filter(
                upload_token__startswith=(
                    DEMO_BATCH_PREFIX
                ),
            ).count()
        )

        with transaction.atomic():
            PaymentRegistry.objects.filter(
                title__startswith=DEMO_PREFIX,
            ).delete()
            demo_invoices.delete()
            InvoiceUploadBatch.objects.filter(
                upload_token__startswith=(
                    DEMO_BATCH_PREFIX
                ),
            ).delete()
            Counterparty.objects.filter(
                external_id_1c__startswith=(
                    DEMO_EXTERNAL_PREFIX
                ),
            ).delete()
            ResponsiblePerson.objects.filter(
                full_name__startswith=DEMO_PREFIX,
            ).delete()

        for storage, name in storage_pairs:
            if name and storage.exists(name):
                storage.delete(name)

        self.stdout.write(
            "RESET DEMO INVOICES: "
            f"{invoice_count}"
        )
        self.stdout.write(
            "RESET DEMO REGISTRIES: "
            f"{registry_count}"
        )
        self.stdout.write(
            "RESET DEMO COUNTERPARTIES: "
            f"{counterparty_count}"
        )
        self.stdout.write(
            "RESET DEMO RESPONSIBLE PEOPLE: "
            f"{responsible_count}"
        )
        self.stdout.write(
            "RESET DEMO UPLOAD BATCHES: "
            f"{batch_count}"
        )

    def _delete_storage_names(
        self,
        names: list[str],
    ) -> None:
        if not names:
            return

        storage = Invoice._meta.get_field(
            "file"
        ).storage

        for name in names:
            if name and storage.exists(name):
                storage.delete(name)
