from django.utils.dateparse import parse_date
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import hashlib
import traceback
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .comment_forms import InvoiceCommentForm
from .comment_models import InvoiceComment
from .counterparty_service import (
    extract_requisites_near_vendor,
    normalize_counterparty_name,
)
from .forms import (
    CounterpartyImportForm,
    CounterpartyManualForm,
    InvoiceCounterpartyAssignForm,
    InvoiceEditForm,
    InvoiceForm,
)
from .log_service import create_invoice_log
from .models import (
    CompanyRequisites,
    Counterparty,
    Invoice,
    InvoiceUploadBatch,
    OCRJob,
)
from .one_c_import_service import import_counterparties_from_file
from .ocr_processing_service import (
    apply_ocr_identity_to_invoice,
    get_duplicate_invoice_by_ocr_identity,
    read_and_parse_invoice_file,
    run_invoice_ocr_processing,
)
from .ocr_verification_service import (
    apply_ocr_amount_to_invoice,
    sync_invoice_amount_verification,
)
from .payment_registry_services import get_active_registry_items_for_invoice

from audit.models import AuditLog
from audit.services import log_action










from .view_modules.counterparty_views import (
    counterparties_missing_requisites,
    counterparty_create,
    counterparty_detail,
    counterparty_directory,
    counterparty_edit,
    export_unmatched_counterparties_excel,
    import_counterparties_1c,
    invoice_assign_counterparty,
    rematch_counterparties_1c,
    unmatched_counterparties,
)

from .view_modules.invoice_views import (
    add_comment,
    calculate_uploaded_file_hash,
    change_invoice_status,
    create_upload_token,
    edit_invoice,
    get_latest_upload_batches_for_user,
    invoice_detail,
    invoice_list,
    render_upload_invoice_form,
    upload_batch_detail,
    upload_batches,
    upload_invoice,
    upload_result,
)

from .view_modules.payment_views import (
    add_invoice_payment,
    cancel_invoice_payment,
)

from .view_modules.payment_registry_views import (
    add_to_payment_registry,
    cancel_payment_registry_view,
    check_payment_registry_view,
    export_payment_registry_1c,
    export_payment_registry_draft_1c,
    export_payment_registry_draft_excel,
    export_payment_registry_excel,
    mark_payment_registry_paid,
    payment_registry,
    payment_registry_detail,
    payment_registry_history,
    payment_schedule,
    remove_from_payment_registry_item,
)

from .view_modules.ocr_views import (
    bulk_repeat_ocr,
    enqueue_ocr_jobs,
    ocr_queue,
    repeat_ocr,
)

from .payment_registry_permissions import (
    require_payment_registry_permission,
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

    from django.db.models import F
    from .models import InvoicePayment

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
    from decimal import Decimal
    from django.db.models import DecimalField, F, Value
    from django.db.models.functions import Coalesce

    from .models import InvoicePayment

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
