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
    from django.utils import timezone

    now = timezone.now()

    items = (
        registry.items
        .select_related(
            "invoice",
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
    )

    for item in items:
        item.status = PaymentRegistryItem.STATUS_PAID
        item.paid_at = now
        item.save(
            update_fields=(
                "status",
                "paid_at",
            )
        )

        invoice = item.invoice
        invoice_update_fields = []

        if hasattr(Invoice, "STATUS_PAID"):
            invoice.status = Invoice.STATUS_PAID
            invoice_update_fields.append(
                "status"
            )

        if _model_has_field(invoice, "paid_at"):
            invoice.paid_at = now
            invoice_update_fields.append(
                "paid_at"
            )

        if invoice_update_fields:
            invoice.save(
                update_fields=tuple(
                    dict.fromkeys(invoice_update_fields)
                )
            )

    registry.status = PaymentRegistry.STATUS_PAID
    registry.save(
        update_fields=(
            "status",
        )
    )

    recalculate_payment_registry(
        registry
    )

    return registry

