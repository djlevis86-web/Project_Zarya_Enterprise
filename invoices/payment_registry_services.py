from decimal import Decimal

from django.db.models import Sum

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
    errors, warnings = validate_invoice_for_payment_registry(invoice)

    if errors:
        return None, errors, warnings

    amount = invoice.amount or getattr(invoice, "ocr_amount", None) or Decimal("0")

    item = PaymentRegistryItem.objects.create(
        registry=registry,
        invoice=invoice,
        amount=amount,
        planned_payment_date=invoice.planned_payment_date,
    )

    recalculate_payment_registry(registry)

    return item, errors, warnings
