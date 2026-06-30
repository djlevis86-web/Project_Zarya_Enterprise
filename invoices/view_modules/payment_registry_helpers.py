from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce

from ..models import InvoicePayment
from ..payment_registry_permissions import (
    user_can_cancel_payment_registry,
    user_can_check_payment_registry,
    user_can_export_payment_registry,
    user_can_manage_payment_registry,
    user_can_mark_payment_registry_paid,
)


def get_payment_registry_permission_context(user):
    return {
        "can_manage_payment_registry": user_can_manage_payment_registry(user),
        "can_check_payment_registry": user_can_check_payment_registry(user),
        "can_export_payment_registry": user_can_export_payment_registry(user),
        "can_mark_payment_registry_paid": user_can_mark_payment_registry_paid(user),
        "can_cancel_payment_registry": user_can_cancel_payment_registry(user),
    }


PAYMENT_STATUS_FILTER_CHOICES = (
    ("", "Все оплаты"),
    ("unpaid", "Не оплачен"),
    ("partial", "Частично оплачен"),
    ("paid", "Оплачен"),
    ("overpaid", "Переплата"),
)


OCR_STATUS_FILTER_CHOICES = (
    ("", "Все OCR-статусы"),
    ("verified", "Сумма подтверждена"),
    ("unverified", "Сумма требует проверки"),
)


def apply_payment_status_filter(queryset, payment_status):
    if not payment_status:
        return queryset

    queryset = queryset.annotate(
        payment_paid_sum=Sum(
            "payments__amount",
            filter=Q(
                payments__status=InvoicePayment.STATUS_POSTED
            )
        )
    )

    if payment_status == "unpaid":
        return queryset.filter(
            Q(payment_paid_sum__isnull=True)
            |
            Q(payment_paid_sum__lte=0)
        )

    if payment_status == "partial":
        return queryset.filter(
            payment_paid_sum__gt=0,
            payment_paid_sum__lt=F("amount")
        )

    if payment_status == "paid":
        return queryset.filter(
            payment_paid_sum=F("amount")
        )

    if payment_status == "overpaid":
        return queryset.filter(
            payment_paid_sum__gt=F("amount")
        )

    return queryset


def apply_ocr_status_filter(queryset, ocr_status):
    if ocr_status == "verified":
        return queryset.filter(
            amount_verified=True
        )

    if ocr_status == "unverified":
        return queryset.filter(
            amount_verified=False
        )

    return queryset


def apply_positive_payment_balance_filter(queryset):
    queryset = queryset.annotate(
        payment_paid_sum=Coalesce(
            Sum(
                "payments__amount",
                filter=Q(
                    payments__status=InvoicePayment.STATUS_POSTED
                )
            ),
            Value(
                Decimal("0.00"),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2
                )
            )
        )
    )

    return queryset.filter(
        payment_paid_sum__lt=F("amount")
    )
