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


def calculate_uploaded_file_hash(uploaded_file):

    uploaded_file.seek(0)

    hasher = hashlib.sha256()

    for chunk in uploaded_file.chunks():
        hasher.update(chunk)

    uploaded_file.seek(0)

    return hasher.hexdigest()


def create_upload_token(request):

    token = uuid.uuid4().hex

    request.session['invoice_upload_token'] = token
    request.session.modified = True

    return token


def get_latest_upload_batches_for_user(user, limit=5):

    batches = (
        InvoiceUploadBatch.objects
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    if not user.is_staff:

        batches = batches.filter(
            user=user
        )

    return batches[:limit]


def render_upload_invoice_form(request, form):

    return render(
        request,
        'invoices/upload_invoice.html',
        {
            'form': form,
            'upload_token': create_upload_token(request),
            'latest_upload_batches': get_latest_upload_batches_for_user(
                request.user
            ),
        }
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


@login_required
def invoice_list(request):

    User = get_user_model()

    invoices = (
        Invoice.objects
        .select_related(
            'user'
        )
        .all()
    )

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    search = request.GET.get(
        'search',
        ''
    ).strip()

    status = request.GET.get(
        'status',
        ''
    )

    user_filter = request.GET.get(
        'user',
        ''
    )

    payment_status_filter = request.GET.get(
        'payment_status',
        ''
    )

    sort = request.GET.get(
        'sort',
        '-created_at'
    )

    if search:

        invoices = invoices.filter(
            Q(title__icontains=search)
            |
            Q(original_filename__icontains=search)
            |
            Q(description__icontains=search)
            |
            Q(vendor__icontains=search)
            |
            Q(invoice_number__icontains=search)
            |
            Q(ocr_text__icontains=search)
            |
            Q(user__username__icontains=search)
        )

    if status:

        invoices = invoices.filter(
            status=status
        )

    if user_filter and request.user.is_staff:

        invoices = invoices.filter(
            user_id=user_filter
        )

    invoices = apply_payment_status_filter(
        invoices,
        payment_status_filter
    )

    allowed_sorts = [
        'id',
        '-id',
        'title',
        '-title',
        'amount',
        '-amount',
        'created_at',
        '-created_at',
    ]

    if sort not in allowed_sorts:

        sort = '-created_at'

    invoices = invoices.order_by(
        sort
    )

    paginator = Paginator(
        invoices,
        15
    )

    page_number = request.GET.get(
        'page'
    )

    page_obj = paginator.get_page(
        page_number
    )

    stats_queryset = Invoice.objects.all()

    if not request.user.is_staff:

        stats_queryset = stats_queryset.filter(
            user=request.user
        )

    total_count = stats_queryset.count()

    new_count = stats_queryset.filter(
        status=Invoice.STATUS_NEW
    ).count()

    review_count = stats_queryset.filter(
        status=Invoice.STATUS_REVIEW
    ).count()

    approved_count = stats_queryset.filter(
        status=Invoice.STATUS_APPROVED
    ).count()

    paid_count = stats_queryset.filter(
        status=Invoice.STATUS_PAID
    ).count()

    rejected_count = stats_queryset.filter(
        status=Invoice.STATUS_REJECTED
    ).count()

    users = User.objects.order_by(
        'username'
    )

    return render(
        request,
        'invoices/invoice_list.html',
        {
            'page_obj': page_obj,
            'search': search,
            'status': status,
            'sort': sort,
            'user_filter': user_filter,
            'payment_status_filter': payment_status_filter,
            'payment_status_choices': PAYMENT_STATUS_FILTER_CHOICES,
            'statuses': Invoice.STATUS_CHOICES,
            'users': users,
            'total_count': total_count,
            'new_count': new_count,
            'review_count': review_count,
            'approved_count': approved_count,
            'paid_count': paid_count,
            'rejected_count': rejected_count,
        }
    )


@login_required
def upload_invoice(request):

    if request.method == 'POST':

        posted_token = request.POST.get(
            'upload_token',
            ''
        )

        session_token = request.session.get(
            'invoice_upload_token',
            ''
        )

        if not session_token or posted_token != session_token:

            messages.warning(
                request,
                'Форма загрузки уже была отправлена. Повторная отправка отменена.'
            )

            if request.session.get(
                'last_upload_result'
            ):

                return redirect(
                    'upload_result'
                )

            return redirect(
                'upload_invoice'
            )

        create_upload_token(
            request
        )

        form = InvoiceForm(
            request.POST,
            request.FILES
        )

        if not form.is_valid():

            messages.error(
                request,
                'Проверьте поля формы.'
            )

            return render_upload_invoice_form(
                request,
                form
            )

        files = request.FILES.getlist(
            'files'
        )

        if not files:

            messages.error(
                request,
                'Выберите хотя бы один файл.'
            )

            return render_upload_invoice_form(
                request,
                form
            )

        if len(files) > 20:

            messages.error(
                request,
                'Максимум 20 файлов за одну загрузку.'
            )

            return render_upload_invoice_form(
                request,
                form
            )

        batch = InvoiceUploadBatch.objects.create(
            user=request.user,
            upload_token=posted_token,
            total_files=len(files),
            status=InvoiceUploadBatch.STATUS_EMPTY
        )

        allowed_extensions = (
            '.pdf',
            '.jpg',
            '.jpeg',
            '.png',
        )

        created_count = 0
        duplicate_files = []
        skipped_files = []

        for uploaded_file in files:

            filename = uploaded_file.name.lower()

            if not filename.endswith(
                allowed_extensions
            ):

                skipped_files.append(
                    uploaded_file.name
                )

                continue

            file_hash = calculate_uploaded_file_hash(
                uploaded_file
            )

            existing_invoice = (
                Invoice.objects
                .filter(
                    file_hash=file_hash
                )
                .order_by(
                    'id'
                )
                .first()
            )

            if existing_invoice:

                duplicate_files.append(
                    {
                        'filename': uploaded_file.name,
                        'invoice_id': existing_invoice.id,
                        'invoice_title': existing_invoice.title,
                    }
                )

                continue

            invoice = Invoice.objects.create(
                user=request.user,
                upload_batch=batch,
                title=form.cleaned_data.get(
                    'title'
                ),
                description=form.cleaned_data.get(
                    'description'
                ),
                amount=form.cleaned_data.get(
                    'amount'
                ) or 0,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_hash=file_hash,
                status=Invoice.STATUS_NEW
            )

            create_invoice_log(
                invoice,
                request.user,
                'Счет загружен'
            )

            log_action(
                request=request,
                action=AuditLog.ACTION_UPLOAD,
                obj=invoice,
                message='Счет загружен.',
                metadata={
                    'filename': uploaded_file.name,
                    'batch_id': batch.id,
                },
            )

            try:

                file_path = invoice.file.path

                print(
                    'OCR FILE:',
                    file_path
                )

                text, parsed = read_and_parse_invoice_file(
                    file_path
                )

                invoice.ocr_text = text

                duplicate_invoice = get_duplicate_invoice_by_ocr_identity(
                    invoice,
                    parsed
                )

                if duplicate_invoice:

                    invoice.delete()

                    duplicate_files.append(
                        {
                            'filename': uploaded_file.name,
                            'invoice_id': duplicate_invoice.id,
                            'invoice_title': duplicate_invoice.title,
                            'duplicate_reason': (
                                'Найден существующий счёт с таким же '
                                'номером и датой.'
                            ),
                        }
                    )

                    continue

                apply_ocr_identity_to_invoice(
                    invoice,
                    parsed
                )

                apply_ocr_amount_to_invoice(
                    invoice,
                    parsed.get(
                        'amount'
                    )
                )

                invoice.save()

                create_invoice_log(
                    invoice,
                    request.user,
                    'OCR обработка завершена'
                )

                print(
                    'OCR SUCCESS:',
                    invoice.id
                )

            except Exception as error:

                print(
                    'OCR ERROR:'
                )

                print(
                    error
                )

                traceback.print_exc()

                create_invoice_log(
                    invoice,
                    request.user,
                    f'OCR ошибка: {error}'
                )

            created_count += 1

        if created_count > 0 and (
            duplicate_files or skipped_files
        ):

            batch_status = InvoiceUploadBatch.STATUS_PARTIAL

        elif created_count > 0:

            batch_status = InvoiceUploadBatch.STATUS_COMPLETED

        else:

            batch_status = InvoiceUploadBatch.STATUS_EMPTY

        batch.uploaded_count = created_count
        batch.duplicate_count = len(
            duplicate_files
        )
        batch.skipped_count = len(
            skipped_files
        )
        batch.duplicate_files = duplicate_files
        batch.skipped_files = skipped_files
        batch.status = batch_status

        batch.save(
            update_fields=[
                'uploaded_count',
                'duplicate_count',
                'skipped_count',
                'duplicate_files',
                'skipped_files',
                'status',
            ]
        )

        request.session['last_upload_result'] = {
            'batch_id': batch.id,
            'uploaded_count': created_count,
            'duplicates': duplicate_files,
            'skipped_files': skipped_files,
        }

        request.session.modified = True

        return redirect(
            'upload_result'
        )

    form = InvoiceForm()

    return render_upload_invoice_form(
        request,
        form
    )


@login_required
def upload_result(request):

    result = request.session.get(
        'last_upload_result',
        {}
    )

    batch = None

    batch_id = result.get(
        'batch_id'
    )

    if batch_id:

        batch = (
            InvoiceUploadBatch.objects
            .filter(
                id=batch_id
            )
            .first()
        )

    return render(
        request,
        'invoices/upload_result.html',
        {
            'batch': batch,
            'uploaded_count': result.get(
                'uploaded_count',
                0
            ),
            'duplicates': result.get(
                'duplicates',
                []
            ),
            'skipped_files': result.get(
                'skipped_files',
                []
            ),
        }
    )


@login_required
def upload_batches(request):

    batches = (
        InvoiceUploadBatch.objects
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    if not request.user.is_staff:

        batches = batches.filter(
            user=request.user
        )

    paginator = Paginator(
        batches,
        20
    )

    page_obj = paginator.get_page(
        request.GET.get(
            'page'
        )
    )

    return render(
        request,
        'invoices/upload_batches.html',
        {
            'page_obj': page_obj,
        }
    )


@login_required
def upload_batch_detail(request, batch_id):

    batch = get_object_or_404(
        InvoiceUploadBatch.objects.select_related(
            'user'
        ),
        id=batch_id
    )

    if not request.user.is_staff and batch.user_id != request.user.id:

        raise PermissionDenied

    invoices = (
        batch.invoices
        .select_related(
            'counterparty',
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    return render(
        request,
        'invoices/upload_batch_detail.html',
        {
            'batch': batch,
            'invoices': invoices,
        }
    )


@login_required
def invoice_detail(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if (
        not request.user.is_staff
        and invoice.user != request.user
    ):

        raise PermissionDenied

    from .forms import InvoicePaymentForm
    from .models import InvoicePayment
    from .payment_services import get_invoice_payment_summary

    payment_summary = get_invoice_payment_summary(
        invoice
    )

    payments = (
        invoice.payments
        .filter(
            status=InvoicePayment.STATUS_POSTED
        )
        .select_related(
            "created_by"
        )
        .order_by(
            "-paid_at",
            "-created_at"
        )
    )

    payment_form = InvoicePaymentForm()

    comments = (
        InvoiceComment.objects
        .filter(
            invoice=invoice
        )
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    comment_form = InvoiceCommentForm()

    return render(
        request,
        'invoices/detail.html',
        {
            'invoice': invoice,
            'logs': invoice.logs.all(),
            'comments': comments,
            'comment_form': comment_form,
            'payment_summary': payment_summary,
            'payments': payments,
            'payment_form': payment_form,
        }
    )













@staff_member_required
def change_invoice_status(request, invoice_id, status):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    allowed_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_REVIEW,
        Invoice.STATUS_APPROVED,
        Invoice.STATUS_PAID,
        Invoice.STATUS_REJECTED,
    ]

    if status not in allowed_statuses:

        messages.error(
            request,
            'Недопустимый статус.'
        )

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id
        )

    old_status = invoice.status
    old_status_label = dict(Invoice.STATUS_CHOICES).get(old_status, old_status)
    new_status_label = dict(Invoice.STATUS_CHOICES).get(status, status)

    invoice.status = status

    invoice.save()

    create_invoice_log(
        invoice,
        request.user,
        f'Статус изменен на "{invoice.get_status_display()}"'
    )

    log_action(
        request=request,
        action=AuditLog.ACTION_UPDATE,
        obj=invoice,
        message=f'Статус счета изменен: {old_status_label} -> {new_status_label}.',
        metadata={
            'field': 'status',
            'old_status': old_status,
            'new_status': status,
            'old_status_label': old_status_label,
            'new_status_label': new_status_label,
        },
    )

    messages.success(
        request,
        'Статус успешно изменен.'
    )

    return redirect(
        'invoice_detail',
        invoice_id=invoice.id
    )


@login_required
def add_comment(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if request.method == 'POST':

        form = InvoiceCommentForm(
            request.POST
        )

        if form.is_valid():

            comment = form.save(
                commit=False
            )

            comment.invoice = invoice
            comment.user = request.user

            comment.save()

            create_invoice_log(
                invoice,
                request.user,
                'Добавлен комментарий'
            )

    return redirect(
        'invoice_detail',
        invoice_id=invoice.id
    )


@staff_member_required
def edit_invoice(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if request.method == 'POST':

        form = InvoiceEditForm(
            request.POST,
            instance=invoice
        )

        if form.is_valid():

            amount_changed = 'amount' in form.changed_data

            invoice = form.save()

            verification_changed, verification_message = sync_invoice_amount_verification(
                invoice,
                source_label='редактирования счёта'
            )

            create_invoice_log(
                invoice,
                request.user,
                'Счет отредактирован'
            )

            if amount_changed or verification_changed:
                create_invoice_log(
                    invoice,
                    request.user,
                    verification_message
                )

                if invoice.amount_verified:
                    messages.success(
                        request,
                        'Сумма подтверждена: совпадает с OCR-суммой.'
                    )
                else:
                    messages.warning(
                        request,
                        'Сумма требует проверки: отличается от OCR-суммы.'
                    )

            if amount_changed:
                active_registry_items = list(
                    get_active_registry_items_for_invoice(
                        invoice
                    )[:5]
                )

                if active_registry_items:
                    registry_numbers = ", ".join(
                        f"№{item.registry_id}"
                        for item in active_registry_items
                    )

                    create_invoice_log(
                        invoice,
                        request.user,
                        (
                            "Сумма счёта изменена при наличии активного "
                            f"реестра оплаты: {registry_numbers}."
                        )
                    )

                    messages.warning(
                        request,
                        (
                            "Счёт уже есть в активном реестре оплаты "
                            f"{registry_numbers}. Проверь реестр повторно: "
                            "сумма строки может быть устаревшей."
                        )
                    )

            messages.success(
                request,
                'Изменения сохранены.'
            )

            return redirect(
                'invoice_detail',
                invoice_id=invoice.id
            )

    else:

        form = InvoiceEditForm(
            instance=invoice
        )

    return render(
        request,
        'invoices/edit_invoice.html',
        {
            'invoice': invoice,
            'form': form,
        }
    )


























@login_required
def unmatched_counterparties(request):

    invoices = (
        Invoice.objects
        .select_related(
            'user'
        )
        .filter(
            counterparty_match_status=Invoice.COUNTERPARTY_MATCH_NOT_FOUND
        )
        .order_by(
            'vendor',
            'id'
        )
    )

    groups_map = {}

    total_amount = Decimal(
        '0.00'
    )

    invoices_count = 0

    for invoice in invoices:

        vendor_name = invoice.vendor or 'Не определен'

        group_key = vendor_name.strip().upper()

        if group_key not in groups_map:

            groups_map[group_key] = {
                'vendor_name': vendor_name,
                'invoices': [],
                'invoice_numbers': [],
                'count': 0,
                'total_amount': Decimal('0.00'),
            }

        amount = invoice.amount or Decimal(
            '0.00'
        )

        groups_map[group_key]['invoices'].append(
            invoice
        )

        groups_map[group_key]['count'] += 1

        groups_map[group_key]['total_amount'] += amount

        if invoice.invoice_number:

            groups_map[group_key]['invoice_numbers'].append(
                invoice.invoice_number
            )

        total_amount += amount

        invoices_count += 1

    groups = sorted(
        groups_map.values(),
        key=lambda item: item['vendor_name']
    )

    return render(
        request,
        'invoices/unmatched_counterparties.html',
        {
            'groups': groups,
            'invoices_count': invoices_count,
            'groups_count': len(groups),
            'total_amount': total_amount,
        }
    )


@login_required
def export_unmatched_counterparties_excel(request):

    invoices = (
        Invoice.objects
        .filter(
            counterparty_match_status=Invoice.COUNTERPARTY_MATCH_NOT_FOUND
        )
        .exclude(
            vendor__isnull=True
        )
        .exclude(
            vendor=''
        )
        .order_by(
            'vendor',
            'id'
        )
    )

    candidates = {}

    for invoice in invoices:

        vendor_name = normalize_counterparty_name(
            invoice.vendor
        )

        if not vendor_name:

            continue

        inn, kpp = extract_requisites_near_vendor(
            invoice.ocr_text or '',
            vendor_name
        )

        key = (
            inn or '',
            kpp or '',
            vendor_name.upper()
        )

        if key not in candidates:

            candidates[key] = {
                'name': vendor_name,
                'inn': inn or '',
                'kpp': kpp or '',
                'invoice_ids': [],
                'invoice_numbers': [],
                'amount_total': Decimal('0.00'),
                'count': 0,
            }

        candidates[key]['invoice_ids'].append(
            str(invoice.id)
        )

        if invoice.invoice_number:

            candidates[key]['invoice_numbers'].append(
                str(invoice.invoice_number)
            )

        candidates[key]['amount_total'] += (
            invoice.amount or Decimal('0.00')
        )

        candidates[key]['count'] += 1

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = 'Кандидаты 1С'

    headers = [
        'Код',
        'Наименование',
        'Полное наименование',
        'ИНН',
        'КПП',
        'Банк',
        'БИК',
        'Расчетный счет',
        'Корреспондентский счет',
        'Активен',
        'Пометка удаления',
        'Количество счетов',
        'ID счетов',
        'Номера счетов',
        'Сумма по счетам',
        'Комментарий',
    ]

    sheet.append(
        headers
    )

    header_fill = PatternFill(
        fill_type='solid',
        fgColor='E5E7EB'
    )

    for cell in sheet[1]:

        cell.font = Font(
            bold=True
        )

        cell.fill = header_fill

        cell.alignment = Alignment(
            horizontal='center',
            vertical='center',
            wrap_text=True
        )

    for candidate in sorted(
        candidates.values(),
        key=lambda item: item['name']
    ):

        sheet.append(
            [
                '',
                candidate['name'],
                candidate['name'],
                candidate['inn'],
                candidate['kpp'],
                '',
                '',
                '',
                '',
                'Да',
                '',
                candidate['count'],
                ', '.join(
                    candidate['invoice_ids']
                ),
                ', '.join(
                    sorted(
                        set(
                            candidate['invoice_numbers']
                        )
                    )
                ),
                candidate['amount_total'],
                'Сформировано из OCR. Нужно сверить с 1С.',
            ]
        )

    for row in sheet.iter_rows():

        for cell in row:

            cell.alignment = Alignment(
                vertical='top',
                wrap_text=True
            )

    column_widths = {
        'A': 18,
        'B': 42,
        'C': 48,
        'D': 16,
        'E': 14,
        'F': 34,
        'G': 14,
        'H': 24,
        'I': 24,
        'J': 12,
        'K': 18,
        'L': 16,
        'M': 28,
        'N': 28,
        'O': 18,
        'P': 42,
    }

    for column_letter, width in column_widths.items():

        sheet.column_dimensions[
            column_letter
        ].width = width

    for row_number in range(
        2,
        sheet.max_row + 1
    ):

        sheet.cell(
            row=row_number,
            column=15
        ).number_format = '#,##0.00'

    sheet.freeze_panes = 'A2'

    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet'
        )
    )

    response[
        'Content-Disposition'
    ] = (
        'attachment; filename="counterparty_candidates_1c.xlsx"'
    )

    workbook.save(
        response
    )

    return response


@staff_member_required
def import_counterparties_1c(request):

    result = None

    if request.method == 'POST':

        form = CounterpartyImportForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            uploaded_file = form.cleaned_data[
                'file'
            ]

            import_dir = Path(
                settings.MEDIA_ROOT
            ) / 'imports_1c'

            import_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            storage = FileSystemStorage(
                location=str(import_dir)
            )

            saved_name = storage.save(
                uploaded_file.name,
                uploaded_file
            )

            file_path = import_dir / saved_name

            result = import_counterparties_from_file(
                file_path=file_path,
                clear_ocr=form.cleaned_data[
                    'clear_ocr'
                ],
                deactivate_missing=form.cleaned_data[
                    'deactivate_missing'
                ]
            )

            messages.success(
                request,
                (
                    'Импорт справочника из 1С завершен. '
                    f'Создано: {result["created"]}, '
                    f'обновлено: {result["updated"]}, '
                    f'пропущено: {result["skipped"]}.'
                )
            )

    else:

        form = CounterpartyImportForm()

    return render(
        request,
        'invoices/import_counterparties_1c.html',
        {
            'form': form,
            'result': result,
        }
    )


@staff_member_required
def rematch_counterparties_1c(request):

    if request.method != 'POST':

        return redirect(
            'unmatched_counterparties'
        )

    from .counterparty_service import get_or_create_counterparty_from_invoice

    invoices = Invoice.objects.all().order_by(
        'id'
    )

    matched = 0
    not_found = 0

    for invoice in invoices:

        invoice.counterparty = None

        counterparty = get_or_create_counterparty_from_invoice(
            invoice
        )

        invoice.counterparty = counterparty

        invoice.save(
            update_fields=[
                'counterparty',
                'counterparty_match_status',
                'counterparty_match_comment',
            ]
        )

        if counterparty:

            matched += 1

        else:

            not_found += 1

    messages.success(
        request,
        (
            'Пересопоставление завершено. '
            f'Найдено: {matched}, '
            f'не найдено: {not_found}.'
        )
    )

    return redirect(
        'unmatched_counterparties'
    )


@staff_member_required
def counterparties_missing_requisites(request):

    payment_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_REVIEW,
        Invoice.STATUS_APPROVED,
    ]

    counterparties = (
        Counterparty.objects
        .filter(
            is_active=True,
            invoices__status__in=payment_statuses
        )
        .filter(
            Q(source=Counterparty.SOURCE_1C)
            |
            Q(source=Counterparty.SOURCE_MANUAL)
        )
        .filter(
            Q(inn__isnull=True)
            |
            Q(inn='')
            |
            Q(bank_name__isnull=True)
            |
            Q(bank_name='')
            |
            Q(bik__isnull=True)
            |
            Q(bik='')
            |
            Q(account_number__isnull=True)
            |
            Q(account_number='')
        )
        .annotate(
            invoices_count=Count(
                'invoices',
                filter=Q(
                    invoices__status__in=payment_statuses
                ),
                distinct=True
            ),
            invoices_total=Sum(
                'invoices__amount',
                filter=Q(
                    invoices__status__in=payment_statuses
                )
            )
        )
        .distinct()
        .order_by(
            'name'
        )
    )

    return render(
        request,
        'invoices/counterparties_missing_requisites.html',
        {
            'counterparties': counterparties,
            'counterparties_count': counterparties.count(),
        }
    )


@staff_member_required
def counterparty_directory(request):

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    source_filter = request.GET.get(
        'source',
        ''
    )

    active_filter = request.GET.get(
        'active',
        'active'
    )

    requisites_filter = request.GET.get(
        'requisites',
        ''
    )

    counterparties = Counterparty.objects.all()

    if active_filter == 'active':

        counterparties = counterparties.filter(
            is_active=True
        )

    elif active_filter == 'inactive':

        counterparties = counterparties.filter(
            is_active=False
        )

    if source_filter:

        counterparties = counterparties.filter(
            source=source_filter
        )

    if search_query:

        counterparties = counterparties.filter(
            Q(name__icontains=search_query)
            |
            Q(full_name__icontains=search_query)
            |
            Q(inn__icontains=search_query)
            |
            Q(kpp__icontains=search_query)
            |
            Q(bank_name__icontains=search_query)
            |
            Q(external_id_1c__icontains=search_query)
        )

    missing_requisites_query = (
        Q(inn__isnull=True)
        |
        Q(inn='')
        |
        Q(bank_name__isnull=True)
        |
        Q(bank_name='')
        |
        Q(bik__isnull=True)
        |
        Q(bik='')
        |
        Q(account_number__isnull=True)
        |
        Q(account_number='')
    )

    if requisites_filter == 'missing':

        counterparties = counterparties.filter(
            missing_requisites_query
        )

    elif requisites_filter == 'complete':

        counterparties = counterparties.exclude(
            missing_requisites_query
        )

    payment_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_REVIEW,
        Invoice.STATUS_APPROVED,
    ]

    counterparties = (
        counterparties
        .annotate(
            invoices_count=Count(
                'invoices',
                distinct=True
            ),
            unpaid_invoices_count=Count(
                'invoices',
                filter=Q(
                    invoices__status__in=payment_statuses
                ),
                distinct=True
            ),
            unpaid_total=Sum(
                'invoices__amount',
                filter=Q(
                    invoices__status__in=payment_statuses
                )
            )
        )
        .order_by(
            'name'
        )
    )

    paginator = Paginator(
        counterparties,
        25
    )

    page_number = request.GET.get(
        'page'
    )

    page_obj = paginator.get_page(
        page_number
    )

    query_params = request.GET.copy()

    if 'page' in query_params:

        query_params.pop(
            'page'
        )

    return render(
        request,
        'invoices/counterparty_directory.html',
        {
            'page_obj': page_obj,
            'search_query': search_query,
            'source_filter': source_filter,
            'active_filter': active_filter,
            'requisites_filter': requisites_filter,
            'source_choices': Counterparty.SOURCE_CHOICES,
            'query_string': query_params.urlencode(),
        }
    )


@staff_member_required
def counterparty_detail(request, counterparty_id):

    counterparty = get_object_or_404(
        Counterparty,
        id=counterparty_id
    )

    invoices = (
        Invoice.objects
        .filter(
            counterparty=counterparty
        )
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    invoices_count = invoices.count()

    unpaid_invoices = invoices.exclude(
        status=Invoice.STATUS_PAID
    )

    unpaid_count = unpaid_invoices.count()

    unpaid_total = (
        unpaid_invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    return render(
        request,
        'invoices/counterparty_detail.html',
        {
            'counterparty': counterparty,
            'invoices': invoices,
            'invoices_count': invoices_count,
            'unpaid_count': unpaid_count,
            'unpaid_total': unpaid_total,
        }
    )


@staff_member_required
def counterparty_create(request):

    if request.method == 'POST':

        form = CounterpartyManualForm(
            request.POST
        )

        if form.is_valid():

            counterparty = form.save(
                commit=False
            )

            counterparty.source = Counterparty.SOURCE_MANUAL

            counterparty.sync_comment = (
                'Создан вручную через интерфейс Project Zarya'
            )

            counterparty.save()

            messages.success(
                request,
                'Контрагент успешно создан.'
            )

            return redirect(
                'counterparty_detail',
                counterparty_id=counterparty.id
            )

    else:

        form = CounterpartyManualForm(
            initial={
                'is_active': True,
            }
        )

    return render(
        request,
        'invoices/counterparty_form.html',
        {
            'form': form,
            'page_title': 'Добавить контрагента',
            'submit_label': 'Создать контрагента',
            'counterparty': None,
        }
    )


@staff_member_required
def counterparty_edit(request, counterparty_id):

    counterparty = get_object_or_404(
        Counterparty,
        id=counterparty_id
    )

    if counterparty.source == Counterparty.SOURCE_1C:

        messages.error(
            request,
            (
                'Контрагента из 1С нельзя редактировать вручную. '
                'Измените данные в 1С и выполните импорт справочника.'
            )
        )

        return redirect(
            'counterparty_detail',
            counterparty_id=counterparty.id
        )

    if request.method == 'POST':

        form = CounterpartyManualForm(
            request.POST,
            instance=counterparty
        )

        if form.is_valid():

            counterparty = form.save(
                commit=False
            )

            counterparty.source = Counterparty.SOURCE_MANUAL

            counterparty.sync_comment = (
                'Обновлен вручную через интерфейс Project Zarya'
            )

            counterparty.save()

            messages.success(
                request,
                'Контрагент успешно обновлен.'
            )

            return redirect(
                'counterparty_detail',
                counterparty_id=counterparty.id
            )

    else:

        form = CounterpartyManualForm(
            instance=counterparty
        )

    return render(
        request,
        'invoices/counterparty_form.html',
        {
            'form': form,
            'page_title': 'Редактировать контрагента',
            'submit_label': 'Сохранить изменения',
            'counterparty': counterparty,
        }
    )


@staff_member_required
def invoice_assign_counterparty(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if request.method == 'POST':

        form = InvoiceCounterpartyAssignForm(
            request.POST
        )

        if form.is_valid():

            counterparty = form.cleaned_data[
                'counterparty'
            ]

            invoice.counterparty = counterparty

            invoice.counterparty_match_status = (
                Invoice.COUNTERPARTY_MATCH_FOUND
            )

            invoice.counterparty_match_comment = (
                f'Контрагент привязан вручную: {counterparty.name}'
            )

            invoice.save(
                update_fields=[
                    'counterparty',
                    'counterparty_match_status',
                    'counterparty_match_comment',
                ]
            )

            create_invoice_log(
                invoice,
                request.user,
                f'Контрагент привязан вручную: {counterparty.name}'
            )

            messages.success(
                request,
                'Контрагент успешно привязан к счету.'
            )

            next_url = request.POST.get(
                'next'
            )

            if next_url:

                return redirect(
                    next_url
                )

            return redirect(
                'invoice_detail',
                invoice_id=invoice.id
            )

    else:

        form = InvoiceCounterpartyAssignForm()

    return render(
        request,
        'invoices/invoice_assign_counterparty.html',
        {
            'invoice': invoice,
            'form': form,
        }
    )
