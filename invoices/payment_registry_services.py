from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .payment_services import create_invoice_payment, get_invoice_payment_summary
from .models import Invoice, PaymentRegistry, PaymentRegistryItem


ACTIVE_REGISTRY_STATUSES = (
    PaymentRegistry.STATUS_DRAFT,
    PaymentRegistry.STATUS_CHECKED,
    PaymentRegistry.STATUS_EXPORTED,
    PaymentRegistry.STATUS_PARTIALLY_PAID,
)


def get_active_registry_item_for_invoice(invoice):
    return (
        PaymentRegistryItem.objects
        .select_related("registry")
        .filter(
            invoice=invoice,
            registry__status__in=ACTIVE_REGISTRY_STATUSES,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .first()
    )


def validate_invoice_for_payment_registry(invoice):
    errors = []
    warnings = []

    duplicate_item = get_active_registry_item_for_invoice(invoice)

    if duplicate_item:
        errors.append(
            f"Счёт уже есть в реестре №{duplicate_item.registry_id}."
        )

    if getattr(invoice, "paid_at", None):
        errors.append(
            "Счёт уже отмечен как оплаченный."
        )

    if hasattr(Invoice, "STATUS_PAID") and invoice.status == Invoice.STATUS_PAID:
        errors.append(
            "Счёт уже находится в статусе оплаты."
        )

    amount = invoice.amount or getattr(invoice, "ocr_amount", None) or Decimal("0")

    if amount <= 0:
        errors.append(
            "Не указана сумма к оплате."
        )

    if not invoice.planned_payment_date:
        warnings.append(
            "Не указана плановая дата оплаты."
        )

    if not invoice.counterparty:
        warnings.append(
            "Контрагент не сопоставлен со справочником."
        )

    if invoice.counterparty:
        missing = []

        for field_name, title in (
            ("inn", "ИНН"),
            ("bank_name", "банк"),
            ("bank_account", "расчётный счёт"),
            ("bik", "БИК"),
        ):
            value = getattr(invoice.counterparty, field_name, "")

            if not value:
                missing.append(title)

        if missing:
            warnings.append(
                "У контрагента не заполнено: " + ", ".join(missing) + "."
            )

    return errors, warnings


def get_or_create_draft_payment_registry(user):
    registry = (
        PaymentRegistry.objects
        .filter(
            status=PaymentRegistry.STATUS_DRAFT,
            created_by=user,
        )
        .order_by("-created_at")
        .first()
    )

    if registry:
        return registry, False

    registry = PaymentRegistry.objects.create(
        created_by=user,
        title="Черновик реестра оплаты",
    )

    return registry, True


def recalculate_payment_registry(registry):
    items = registry.items.exclude(
        status=PaymentRegistryItem.STATUS_CANCELLED
    )

    total_amount = (
        items.aggregate(
            total=Sum("amount")
        ).get("total")
        or Decimal("0")
    )

    registry.items_count = items.count()
    registry.total_amount = total_amount
    registry.save(
        update_fields=(
            "items_count",
            "total_amount",
        )
    )

    return registry


def add_invoice_to_payment_registry(invoice, registry):
    errors = []
    warnings = []

    # registry может прийти как объект, как id или как tuple от get_or_create.
    if isinstance(registry, tuple):
        registry = registry[0]

    registry_id = getattr(
        registry,
        "id",
        registry,
    )

    registry_obj = registry

    if not hasattr(
        registry_obj,
        "id",
    ):
        registry_obj = PaymentRegistry.objects.get(
            id=registry_id
        )

    validation_errors, validation_warnings = validate_invoice_for_payment_registry(
        invoice
    )

    errors.extend(validation_errors)
    warnings.extend(validation_warnings)

    summary = get_invoice_payment_summary(
        invoice
    )

    remaining_amount = summary["remaining_amount"]

    if remaining_amount <= 0:
        errors.append(
            "Счёт уже полностью оплачен или имеет переплату."
        )

    if errors:
        return None, errors, warnings

    existing_item = (
        PaymentRegistryItem.objects
        .filter(
            registry_id=registry_id,
            invoice_id=invoice.id,
        )
        .first()
    )

    if existing_item:
        if existing_item.status == PaymentRegistryItem.STATUS_CANCELLED:
            existing_item.status = PaymentRegistryItem.STATUS_ADDED
            existing_item.amount = remaining_amount
            existing_item.planned_payment_date = getattr(
                invoice,
                "planned_payment_date",
                None,
            )
            existing_item.save(
                update_fields=[
                    "status",
                    "amount",
                    "planned_payment_date",
                ]
            )

            recalculate_payment_registry(
                registry_obj
            )

            warnings.append(
                "Счёт был ранее удалён из черновика и теперь восстановлен."
            )

            return existing_item, errors, warnings

        warnings.append(
            "Счёт уже есть в текущем черновике реестра."
        )

        return existing_item, errors, warnings

    item = PaymentRegistryItem.objects.create(
        registry_id=registry_id,
        invoice_id=invoice.id,
        amount=remaining_amount,
        planned_payment_date=getattr(
            invoice,
            "planned_payment_date",
            None,
        ),
    )

    recalculate_payment_registry(
        registry_obj
    )

    return item, errors, warnings

def check_payment_registry(registry):
    items = (
        registry.items
        .select_related(
            "invoice",
            "invoice__counterparty",
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            "planned_payment_date",
            "invoice_id",
        )
    )

    errors = []
    warnings = []
    ready_count = 0

    for item in items:
        invoice = item.invoice
        counterparty = invoice.counterparty

        row_errors = []
        row_warnings = []

        if not item.amount or item.amount <= 0:
            row_errors.append(
                "не указана сумма"
            )

        payment_date = item.planned_payment_date or invoice.planned_payment_date

        if not payment_date:
            row_errors.append(
                "не указана дата оплаты"
            )

        duplicate_item = (
            PaymentRegistryItem.objects
            .select_related(
                "registry"
            )
            .filter(
                invoice=invoice,
                registry__status__in=ACTIVE_REGISTRY_STATUSES,
            )
            .exclude(
                registry=registry
            )
            .exclude(
                status=PaymentRegistryItem.STATUS_CANCELLED
            )
            .first()
        )

        if duplicate_item:
            row_errors.append(
                f"уже есть в реестре №{duplicate_item.registry_id}"
            )

        if not counterparty:
            row_errors.append(
                "контрагент не сопоставлен со справочником"
            )
        else:
            missing_fields = []

            for field_name, title in (
                ("inn", "ИНН"),
                ("bank_name", "банк"),
                ("bank_account", "расчётный счёт"),
                ("bik", "БИК"),
            ):
                value = getattr(
                    counterparty,
                    field_name,
                    ""
                )

                if not value:
                    missing_fields.append(
                        title
                    )

            if missing_fields:
                row_errors.append(
                    "не заполнено: " + ", ".join(missing_fields)
                )

        if row_errors:
            errors.append(
                {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number or "",
                    "messages": row_errors,
                }
            )
        else:
            ready_count += 1

        if row_warnings:
            warnings.append(
                {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number or "",
                    "messages": row_warnings,
                }
            )

    return {
        "items_count": items.count(),
        "ready_count": ready_count,
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def _model_has_field(instance, field_name):
    try:
        instance._meta.get_field(field_name)
        return True
    except Exception:
        return False


def mark_payment_registry_as_paid(registry, user=None):
    today = timezone.localdate()

    paid_count = 0
    skipped_count = 0

    items = (
        registry.items
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .select_related(
            "invoice"
        )
    )

    for item in items:
        summary = get_invoice_payment_summary(
            item.invoice
        )

        remaining_amount = summary["remaining_amount"]

        if remaining_amount <= 0:
            item.status = PaymentRegistryItem.STATUS_PAID
            item.paid_at = today
            item.save(
                update_fields=[
                    "status",
                    "paid_at",
                ]
            )

            skipped_count += 1
            continue

        payment_amount = item.amount

        if payment_amount > remaining_amount:
            payment_amount = remaining_amount

        create_invoice_payment(
            invoice=item.invoice,
            amount=payment_amount,
            user=user,
            registry_item=item,
            paid_at=today,
            payment_number=f"Реестр №{registry.id}",
            comment="Оплата по реестру",
            source="registry",
        )

        item.status = PaymentRegistryItem.STATUS_PAID
        item.paid_at = today
        item.save(
            update_fields=[
                "status",
                "paid_at",
            ]
        )

        paid_count += 1

    registry.status = PaymentRegistry.STATUS_PAID
    registry.save(
        update_fields=[
            "status",
        ]
    )

    recalculate_payment_registry(
        registry
    )

    return {
        "paid_count": paid_count,
        "skipped_count": skipped_count,
    }

def cancel_payment_registry(registry, user=None, reason=""):
    allowed_statuses = (
        PaymentRegistry.STATUS_DRAFT,
        PaymentRegistry.STATUS_CHECKED,
    )

    if registry.status not in allowed_statuses:
        return False

    if reason:
        old_comment = registry.comment or ""
        registry.comment = (
            old_comment
            + ("\n" if old_comment else "")
            + f"Отменён. Причина: {reason}"
        )

    registry.status = PaymentRegistry.STATUS_CANCELLED
    registry.save(
        update_fields=(
            "status",
            "comment",
        )
    )

    return True

