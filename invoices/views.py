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

from ocr.services import (
    extract_text_from_image,
    extract_text_from_pdf,
    parse_invoice_data,
)

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

                if file_path.lower().endswith(
                    '.pdf'
                ):

                    text = extract_text_from_pdf(
                        file_path
                    )

                else:

                    text = extract_text_from_image(
                        file_path
                    )

                invoice.ocr_text = text

                parsed = parse_invoice_data(
                    text
                )

                invoice.invoice_number = parsed.get(
                    'invoice_number'
                )

                invoice.invoice_date = parsed.get(
                    'invoice_date'
                )

                if invoice.invoice_number and invoice.invoice_date:

                    exists_invoice = (
                        Invoice.objects
                        .filter(
                            invoice_number=invoice.invoice_number,
                            invoice_date=invoice.invoice_date,
                        )
                        .exclude(
                            id=invoice.id
                        )
                        .exclude(
                            status=Invoice.STATUS_REJECTED
                        )
                        .order_by(
                            'id'
                        )
                        .first()
                    )

                    if exists_invoice:

                        invoice.delete()

                        duplicate_files.append(
                            {
                                'filename': uploaded_file.name,
                                'invoice_id': exists_invoice.id,
                                'invoice_title': exists_invoice.title,
                                'duplicate_reason': (
                                    'Найден существующий счёт с таким же '
                                    'номером и датой.'
                                ),
                            }
                        )

                        continue

                invoice.vendor = parsed.get(
                    'vendor'
                )

                amount = parsed.get(
                    'amount'
                )

                if amount:

                    try:

                        invoice.ocr_amount = float(
                            str(amount).replace(
                                ',',
                                '.'
                            )
                        )

                        if (
                            invoice.amount is None
                            or
                            float(invoice.amount) == 0
                        ):

                            invoice.amount = invoice.ocr_amount
                            invoice.amount_verified = True
                            invoice.ocr_verified = True

                        else:

                            invoice.amount_verified = (
                                float(invoice.amount)
                                ==
                                float(invoice.ocr_amount)
                            )

                            invoice.ocr_verified = (
                                invoice.amount_verified
                            )

                    except Exception:

                        invoice.amount_verified = False

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



@login_required
def repeat_ocr(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if (
        not request.user.is_staff
        and invoice.user_id != request.user.id
    ):

        raise PermissionDenied

    if request.method != 'POST':

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id
        )

    if not invoice.file:

        messages.error(
            request,
            'У счета нет файла для OCR.'
        )

        return redirect(
            'invoice_detail',
            invoice_id=invoice.id
        )

    try:

        file_path = invoice.file.path

        if file_path.lower().endswith(
            '.pdf'
        ):

            text = extract_text_from_pdf(
                file_path
            )

        else:

            text = extract_text_from_image(
                file_path
            )

        parsed = parse_invoice_data(
            text
        )

        invoice.ocr_text = text

        parsed_invoice_number = parsed.get(
            'invoice_number'
        )

        parsed_invoice_date = parsed.get(
            'invoice_date'
        )

        number_warning = ''

        if parsed_invoice_number and parsed_invoice_date:

            duplicate_invoice = (
                Invoice.objects
                .filter(
                    invoice_number=parsed_invoice_number,
                    invoice_date=parsed_invoice_date,
                )
                .exclude(
                    id=invoice.id
                )
                .exclude(
                    status=Invoice.STATUS_REJECTED
                )
                .first()
            )

            if duplicate_invoice:

                number_warning = (
                    f'OCR нашел номер {parsed_invoice_number} '
                    f'от {parsed_invoice_date}, '
                    f'но такой счет уже есть: #{duplicate_invoice.id}. '
                    'Номер текущего счета не изменен.'
                )

            else:

                invoice.invoice_number = parsed_invoice_number

        elif parsed_invoice_number:

            invoice.invoice_number = parsed_invoice_number

        else:

            invoice.invoice_number = None

        invoice.invoice_date = parsed_invoice_date

        invoice.vendor = parsed.get(
            'vendor'
        )

        amount = parsed.get(
            'amount'
        )

        amount_warning = ''

        if amount:

            try:

                ocr_amount = Decimal(
                    str(amount).replace(
                        ',',
                        '.'
                    )
                )

                invoice.ocr_amount = ocr_amount

                current_amount = invoice.amount or Decimal(
                    '0.00'
                )

                if current_amount == Decimal(
                    '0.00'
                ):

                    invoice.amount = ocr_amount
                    invoice.amount_verified = True
                    invoice.ocr_verified = True

                else:

                    invoice.amount_verified = (
                        Decimal(str(current_amount))
                        ==
                        ocr_amount
                    )

                    invoice.ocr_verified = invoice.amount_verified

            except Exception:

                invoice.ocr_amount = None
                invoice.amount_verified = False
                invoice.ocr_verified = False

                amount_warning = (
                    'OCR нашел сумму, но не удалось преобразовать ее в число.'
                )

        else:

            invoice.ocr_amount = None
            invoice.amount_verified = False
            invoice.ocr_verified = False

            amount_warning = 'OCR сумма не определена.'

        ocr_comments = [
            'OCR повторно выполнен вручную.'
        ]

        if number_warning:

            ocr_comments.append(
                number_warning
            )

        if amount_warning:

            ocr_comments.append(
                amount_warning
            )

        invoice.ocr_comment = ' '.join(
            ocr_comments
        )

        invoice.save()

        try:

            from .counterparty_service import get_or_create_counterparty_from_invoice

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

        except Exception as match_error:

            create_invoice_log(
                invoice,
                request.user,
                f'Ошибка сопоставления контрагента после повторного OCR: {match_error}'
            )

        create_invoice_log(
            invoice,
            request.user,
            'OCR повторно выполнен'
        )

        log_action(
            request=request,
            action=AuditLog.ACTION_OCR,
            obj=invoice,
            message='OCR повторно выполнен вручную.',
            metadata={
                'mode': 'single',
            },
        )

        messages.success(
            request,
            'OCR успешно обновлен.'
        )

        if number_warning:

            messages.warning(
                request,
                number_warning
            )

    except Exception as error:

        traceback.print_exc()

        create_invoice_log(
            invoice,
            request.user,
            f'OCR повторная ошибка: {error}'
        )

        log_action(
            request=request,
            action=AuditLog.ACTION_OCR,
            obj=invoice,
            message=f'OCR повторно не выполнен: {error}',
            metadata={
                'mode': 'single',
                'error': str(error),
            },
        )

        messages.error(
            request,
            f'OCR не выполнен: {error}'
        )

    return redirect(
        'invoice_detail',
        invoice_id=invoice.id
    )


def run_invoice_ocr_processing(invoice, user, log_action):

    if not invoice.file:

        create_invoice_log(
            invoice,
            user,
            'OCR не выполнен: у счета нет файла'
        )

        return False, 'у счета нет файла'

    try:

        file_path = invoice.file.path

        if file_path.lower().endswith(
            '.pdf'
        ):

            text = extract_text_from_pdf(
                file_path
            )

        else:

            text = extract_text_from_image(
                file_path
            )

        parsed = parse_invoice_data(
            text
        )

        invoice.ocr_text = text

        parsed_invoice_number = parsed.get(
            'invoice_number'
        )

        parsed_invoice_date = parsed.get(
            'invoice_date'
        )

        number_warning = ''

        if parsed_invoice_number and parsed_invoice_date:

            duplicate_invoice = (
                Invoice.objects
                .filter(
                    invoice_number=parsed_invoice_number,
                    invoice_date=parsed_invoice_date,
                )
                .exclude(
                    id=invoice.id
                )
                .exclude(
                    status=Invoice.STATUS_REJECTED
                )
                .first()
            )

            if duplicate_invoice:

                number_warning = (
                    f'OCR нашел номер {parsed_invoice_number} '
                    f'от {parsed_invoice_date}, '
                    f'но такой счет уже есть: #{duplicate_invoice.id}. '
                    'Номер текущего счета не изменен.'
                )

            else:

                invoice.invoice_number = parsed_invoice_number

        elif parsed_invoice_number:

            invoice.invoice_number = parsed_invoice_number

        else:

            invoice.invoice_number = None

        invoice.invoice_date = parsed_invoice_date

        invoice.vendor = parsed.get(
            'vendor'
        )

        amount = parsed.get(
            'amount'
        )

        amount_warning = ''

        if amount:

            try:

                ocr_amount = Decimal(
                    str(amount).replace(
                        ',',
                        '.'
                    )
                )

                invoice.ocr_amount = ocr_amount

                current_amount = invoice.amount or Decimal(
                    '0.00'
                )

                if current_amount == Decimal(
                    '0.00'
                ):

                    invoice.amount = ocr_amount
                    invoice.amount_verified = True
                    invoice.ocr_verified = True

                else:

                    invoice.amount_verified = (
                        Decimal(str(current_amount))
                        ==
                        ocr_amount
                    )

                    invoice.ocr_verified = invoice.amount_verified

            except Exception:

                invoice.ocr_amount = None
                invoice.amount_verified = False
                invoice.ocr_verified = False

                amount_warning = (
                    'OCR нашел сумму, но не удалось преобразовать ее в число.'
                )

        else:

            invoice.ocr_amount = None
            invoice.amount_verified = False
            invoice.ocr_verified = False

            amount_warning = 'OCR сумма не определена.'

        ocr_comments = [
            log_action
        ]

        if number_warning:

            ocr_comments.append(
                number_warning
            )

        if amount_warning:

            ocr_comments.append(
                amount_warning
            )

        invoice.ocr_comment = ' '.join(
            ocr_comments
        )

        invoice.save()

        try:

            from .counterparty_service import get_or_create_counterparty_from_invoice

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

        except Exception as match_error:

            create_invoice_log(
                invoice,
                user,
                f'Ошибка сопоставления контрагента после OCR: {match_error}'
            )

        create_invoice_log(
            invoice,
            user,
            log_action
        )

        if number_warning:

            return True, number_warning

        return True, 'OCR успешно обновлен'

    except Exception as error:

        traceback.print_exc()

        create_invoice_log(
            invoice,
            user,
            f'OCR ошибка: {error}'
        )

        return False, str(error)


@login_required
def bulk_repeat_ocr(request):

    if request.method != 'POST':

        return redirect(
            'invoice_list'
        )

    next_url = request.POST.get(
        'next',
        ''
    )

    invoice_ids = [
        item
        for item in request.POST.getlist(
            'invoice_ids'
        )
        if item
    ]

    if not invoice_ids:

        messages.warning(
            request,
            'Выберите хотя бы один счет для повторного OCR.'
        )

        if next_url.startswith(
            '/'
        ):

            return redirect(
                next_url
            )

        return redirect(
            'invoice_list'
        )

    invoices = (
        Invoice.objects
        .filter(
            id__in=invoice_ids
        )
        .select_related(
            'user',
            'counterparty'
        )
        .order_by(
            'id'
        )
    )

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    allowed_count = invoices.count()
    requested_count = len(
        invoice_ids
    )

    if allowed_count == 0:

        messages.error(
            request,
            'Нет доступных счетов для повторного OCR.'
        )

        if next_url.startswith(
            '/'
        ):

            return redirect(
                next_url
            )

        return redirect(
            'invoice_list'
        )

    success_count = 0
    error_items = []
    warning_items = []

    for invoice in invoices:

        ok, message = run_invoice_ocr_processing(
            invoice,
            request.user,
            'OCR повторно выполнен массово'
        )

        if ok:

            success_count += 1

            if message and message != 'OCR успешно обновлен':

                warning_items.append(
                    f'#{invoice.id}: {message}'
                )

        else:

            error_items.append(
                f'#{invoice.id}: {message}'
            )

    log_action(
        request=request,
        action=AuditLog.ACTION_OCR,
        object_type='Invoice',
        object_repr='Массовый OCR',
        message='Массовый OCR выбранных счетов выполнен.',
        metadata={
            'mode': 'bulk',
            'requested_count': requested_count,
            'allowed_count': allowed_count,
            'success_count': success_count,
            'error_count': len(error_items),
            'warning_count': len(warning_items),
            'requested_invoice_ids': invoice_ids,
        },
    )

    if success_count:

        messages.success(
            request,
            f'OCR выполнен для счетов: {success_count}.'
        )

    if requested_count != allowed_count:

        messages.warning(
            request,
            (
                'Часть выбранных счетов была пропущена: '
                'нет доступа или счет не найден.'
            )
        )

    if warning_items:

        messages.warning(
            request,
            'Предупреждения OCR: ' + ' | '.join(
                warning_items[:5]
            )
        )

    if error_items:

        messages.error(
            request,
            'Ошибки OCR: ' + ' | '.join(
                error_items[:5]
            )
        )

    if next_url.startswith(
        '/'
    ):

        return redirect(
            next_url
        )

    return redirect(
        'invoice_list'
    )




@login_required
def enqueue_ocr_jobs(request):

    if request.method != 'POST':

        return redirect(
            'invoice_list'
        )

    next_url = request.POST.get(
        'next',
        ''
    )

    invoice_ids = request.POST.getlist(
        'invoice_ids'
    )

    single_invoice_id = request.POST.get(
        'invoice_id'
    )

    if single_invoice_id:

        invoice_ids.append(
            single_invoice_id
        )

    invoice_ids = [
        item
        for item in invoice_ids
        if item
    ]

    if not invoice_ids:

        messages.warning(
            request,
            'Выберите хотя бы один счет для постановки OCR в очередь.'
        )

        if next_url.startswith(
            '/'
        ):

            return redirect(
                next_url
            )

        return redirect(
            'invoice_list'
        )

    invoices = (
        Invoice.objects
        .filter(
            id__in=invoice_ids
        )
        .select_related(
            'user'
        )
        .order_by(
            'id'
        )
    )

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    created_count = 0
    skipped_count = 0

    for invoice in invoices:

        existing_job = (
            OCRJob.objects
            .filter(
                invoice=invoice,
                status__in=[
                    OCRJob.STATUS_PENDING,
                    OCRJob.STATUS_PROCESSING,
                ]
            )
            .first()
        )

        if existing_job:

            skipped_count += 1

            continue

        OCRJob.objects.create(
            invoice=invoice,
            user=request.user,
            status=OCRJob.STATUS_PENDING,
            source=OCRJob.SOURCE_BULK,
        )

        create_invoice_log(
            invoice,
            request.user,
            'OCR поставлен в очередь'
        )

        created_count += 1

    if created_count:

        messages.success(
            request,
            f'OCR поставлен в очередь: {created_count}.'
        )

    if skipped_count:

        messages.warning(
            request,
            f'Пропущено, уже есть активная OCR задача: {skipped_count}.'
        )

    if next_url.startswith(
        '/'
    ):

        return redirect(
            next_url
        )

    return redirect(
        'ocr_queue'
    )


@login_required
def ocr_queue(request):

    selected_status = request.GET.get(
        'status',
        ''
    )

    jobs = (
        OCRJob.objects
        .select_related(
            'invoice',
            'user',
            'invoice__counterparty',
        )
        .order_by(
            '-created_at'
        )
    )

    if not request.user.is_staff:

        jobs = jobs.filter(
            user=request.user
        )

    if selected_status:

        jobs = jobs.filter(
            status=selected_status
        )

    stats_queryset = OCRJob.objects.all()

    if not request.user.is_staff:

        stats_queryset = stats_queryset.filter(
            user=request.user
        )

    pending_count = stats_queryset.filter(
        status=OCRJob.STATUS_PENDING
    ).count()

    processing_count = stats_queryset.filter(
        status=OCRJob.STATUS_PROCESSING
    ).count()

    done_count = stats_queryset.filter(
        status=OCRJob.STATUS_DONE
    ).count()

    error_count = stats_queryset.filter(
        status=OCRJob.STATUS_ERROR
    ).count()

    paginator = Paginator(
        jobs,
        25
    )

    page_obj = paginator.get_page(
        request.GET.get(
            'page'
        )
    )

    return render(
        request,
        'invoices/ocr_queue.html',
        {
            'page_obj': page_obj,
            'selected_status': selected_status,
            'status_choices': OCRJob.STATUS_CHOICES,
            'pending_count': pending_count,
            'processing_count': processing_count,
            'done_count': done_count,
            'error_count': error_count,
        }
    )

@login_required
def cancel_invoice_payment(request, payment_id):
    from .models import InvoicePayment
    from .payment_services import get_invoice_payment_summary

    payment = get_object_or_404(
        InvoicePayment.objects.select_related(
            "invoice"
        ),
        id=payment_id
    )

    invoice = payment.invoice

    if (
        not request.user.is_staff
        and not request.user.is_superuser
        and invoice.user_id != request.user.id
    ):
        raise PermissionDenied

    if request.method != "POST":
        return redirect(
            "invoice_detail",
            invoice_id=invoice.id
        )

    if payment.status == InvoicePayment.STATUS_CANCELLED:
        messages.warning(
            request,
            "Эта оплата уже отменена."
        )

        return redirect(
            "invoice_detail",
            invoice_id=invoice.id
        )

    payment.status = InvoicePayment.STATUS_CANCELLED
    payment.comment = (
        (payment.comment or "")
        + "\nОтменено пользователем: "
        + request.user.get_username()
    ).strip()

    payment.save(
        update_fields=[
            "status",
            "comment",
            "updated_at",
        ]
    )

    create_invoice_log(
        invoice,
        request.user,
        f"Отменена оплата по счёту: {payment.amount}"
    )

    get_invoice_payment_summary(
        invoice
    )

    messages.success(
        request,
        "Оплата отменена. Остаток по счёту пересчитан."
    )

    return redirect(
        "invoice_detail",
        invoice_id=invoice.id
    )


@login_required
def add_invoice_payment(request, invoice_id):
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if (
        not request.user.is_staff
        and not request.user.is_superuser
        and invoice.user_id != request.user.id
    ):
        raise PermissionDenied

    if request.method != "POST":
        return redirect(
            "invoice_detail",
            invoice_id=invoice.id
        )

    from .forms import InvoicePaymentForm
    from .payment_services import create_invoice_payment

    form = InvoicePaymentForm(
        request.POST
    )

    if not form.is_valid():
        messages.error(
            request,
            "Проверьте данные оплаты."
        )

        return redirect(
            "invoice_detail",
            invoice_id=invoice.id
        )

    try:
        payment, updated_summary = create_invoice_payment(
            invoice=invoice,
            amount=form.cleaned_data["amount"],
            user=request.user,
            paid_at=form.cleaned_data["paid_at"],
            payment_number=form.cleaned_data.get("payment_number") or "",
            comment=form.cleaned_data.get("comment") or "",
        )
    except ValueError as error:
        messages.error(
            request,
            str(error)
        )

        return redirect(
            "invoice_detail",
            invoice_id=invoice.id
        )

    create_invoice_log(
        invoice,
        request.user,
        f"Внесена оплата по счёту: {payment.amount}"
    )

    if updated_summary["remaining_amount"] <= 0:
        create_invoice_log(
            invoice,
            request.user,
            "Счёт полностью закрыт по оплате"
        )

    messages.success(
        request,
        "Оплата успешно внесена."
    )

    return redirect(
        "invoice_detail",
        invoice_id=invoice.id
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

            form.save()

            create_invoice_log(
                invoice,
                request.user,
                'Счет отредактирован'
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
def payment_schedule(request):

    filter_type = request.GET.get(
        'filter',
        'all'
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    selected_status = request.GET.get(
        'status',
        'payment'
    )

    selected_priority = request.GET.get(
        'priority',
        ''
    )

    schedule_payment_status_filter = request.GET.get(
        'payment_status',
        ''
    )

    date_from = request.GET.get(
        'date_from',
        ''
    )

    date_to = request.GET.get(
        'date_to',
        ''
    )

    parsed_date_from = parse_date(date_from) if date_from else None

    parsed_date_to = parse_date(date_to) if date_to else None

    payment_statuses = [
        Invoice.STATUS_NEW,
        Invoice.STATUS_REVIEW,
        Invoice.STATUS_APPROVED,
    ]

    base_invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .filter(
            status__in=payment_statuses
        )
    )

    today = date.today()

    week_end = today + timedelta(
        days=7
    )

    month_end = today + timedelta(
        days=30
    )

    total_count = base_invoices.count()

    today_count = base_invoices.filter(
        planned_payment_date=today
    ).count()

    week_count = base_invoices.filter(
        planned_payment_date__gte=today,
        planned_payment_date__lte=week_end
    ).count()

    month_count = base_invoices.filter(
        planned_payment_date__gte=today,
        planned_payment_date__lte=month_end
    ).count()

    overdue_count = base_invoices.filter(
        planned_payment_date__lt=today
    ).count()

    no_date_count = base_invoices.filter(
        planned_payment_date__isnull=True
    ).count()

    total_amount = (
        base_invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    invoices = base_invoices

    if filter_type == 'today':

        invoices = invoices.filter(
            planned_payment_date=today
        )

    elif filter_type == 'week':

        invoices = invoices.filter(
            planned_payment_date__gte=today,
            planned_payment_date__lte=week_end
        )

    elif filter_type == 'month':

        invoices = invoices.filter(
            planned_payment_date__gte=today,
            planned_payment_date__lte=month_end
        )

    elif filter_type == 'overdue':

        invoices = invoices.filter(
            planned_payment_date__lt=today
        )

    elif filter_type == 'no_date':

        invoices = invoices.filter(
            planned_payment_date__isnull=True
        )

    if selected_status and selected_status not in [
        'payment',
        'all',
    ]:

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_priority:

        invoices = invoices.filter(
            payment_priority=selected_priority
        )

    invoices = apply_payment_status_filter(
        invoices,
        schedule_payment_status_filter
    )

    if parsed_date_from and filter_type != 'no_date':

        invoices = invoices.filter(
            planned_payment_date__gte=parsed_date_from
        )

    if parsed_date_to and filter_type != 'no_date':

        invoices = invoices.filter(
            planned_payment_date__lte=parsed_date_to
        )

    if search_query:

        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(title__icontains=search_query)
            |
            Q(description__icontains=search_query)
        )

    filtered_count = invoices.count()

    filtered_amount = (
        invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    priority_field = Invoice._meta.get_field(
        'payment_priority'
    )

    priority_choices = list(
        priority_field.choices or []
    )

    if not priority_choices:

        priority_choices = [
            (
                item,
                item
            )
            for item in (
                base_invoices
                .exclude(
                    payment_priority__isnull=True
                )
                .order_by(
                    '-payment_priority'
                )
                .values_list(
                    'payment_priority',
                    flat=True
                )
                .distinct()
            )
        ]

    invoices = apply_positive_payment_balance_filter(
        invoices
    )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
    )

    return render(
        request,
        'invoices/payment_schedule.html',
        {
            'invoices': invoices,
            'today': today,
            'week_end': week_end,
            'month_end': month_end,
            'filter_type': filter_type,
            'search_query': search_query,
            'selected_status': selected_status,
            'selected_priority': selected_priority,
            'schedule_payment_status_filter': schedule_payment_status_filter,
            'payment_status_choices': PAYMENT_STATUS_FILTER_CHOICES,
            'date_from': date_from,
            'date_to': date_to,
            'status_choices': Invoice.STATUS_CHOICES,
            'priority_choices': priority_choices,
            'total_count': total_count,
            'today_count': today_count,
            'week_count': week_count,
            'month_count': month_count,
            'overdue_count': overdue_count,
            'no_date_count': no_date_count,
            'total_amount': total_amount,
            'filtered_count': filtered_count,
            'filtered_amount': filtered_amount,
        }
    )

@login_required
@require_payment_registry_permission(
    user_can_manage_payment_registry,
    'Нет прав на добавление счетов в реестр оплаты.',
)
def add_to_payment_registry(request):

    if request.method != 'POST':

        messages.warning(
            request,
            'Добавлять счета в реестр можно только из формы.'
        )

        return redirect(
            'payment_schedule'
        )

    invoice_ids = request.POST.getlist(
        'invoice_ids'
    )

    if not invoice_ids:

        messages.warning(
            request,
            'Выбери хотя бы один счет для добавления в реестр.'
        )

        return redirect(
            'payment_schedule'
        )

    from .payment_registry_services import (
        add_invoice_to_payment_registry,
        get_or_create_draft_payment_registry,
    )

    registry, created = get_or_create_draft_payment_registry(
        request.user
    )

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .filter(
            id__in=invoice_ids
        )
    )

    added_count = 0
    skipped_messages = []
    warning_messages = []

    for invoice in invoices:

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry
        )

        if item:

            added_count += 1

        if errors:

            skipped_messages.append(
                f'#{invoice.id}: ' + '; '.join(errors)
            )

        if warnings:

            warning_messages.append(
                f'#{invoice.id}: ' + '; '.join(warnings)
            )

    if added_count:

        messages.success(
            request,
            f'Добавлено счетов в реестр №{registry.id}: {added_count}.'
        )

    if skipped_messages:

        messages.warning(
            request,
            'Не добавлено: ' + ' | '.join(skipped_messages[:5])
        )

    if warning_messages:

        messages.info(
            request,
            'Предупреждения: ' + ' | '.join(warning_messages[:5])
        )

    if created and not added_count:

        registry.delete()

    return redirect(
        'payment_registry'
    )


@login_required
@require_payment_registry_permission(
    user_can_manage_payment_registry,
    'Нет прав на удаление счетов из черновика реестра.',
)
def remove_from_payment_registry_item(request, item_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Удалять счета из черновика можно только из формы.'
        )

        return redirect(
            'payment_registry'
        )

    from .models import PaymentRegistry, PaymentRegistryItem
    from .payment_registry_services import recalculate_payment_registry

    item = (
        PaymentRegistryItem.objects
        .select_related(
            'registry',
            'invoice',
        )
        .filter(
            id=item_id,
            registry__status=PaymentRegistry.STATUS_DRAFT,
            registry__created_by=request.user,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .first()
    )

    if not item:

        messages.warning(
            request,
            'Строка реестра не найдена или уже удалена.'
        )

        return redirect(
            'payment_registry'
        )

    registry = item.registry
    invoice_id = item.invoice_id

    item.status = PaymentRegistryItem.STATUS_CANCELLED
    item.save(
        update_fields=(
            'status',
        )
    )

    recalculate_payment_registry(
        registry
    )

    messages.success(
        request,
        f'Счёт #{invoice_id} удалён из черновика реестра №{registry.id}.'
    )

    return redirect(
        'payment_registry'
    )


@login_required
@require_payment_registry_permission(
    user_can_check_payment_registry,
    'Нет прав на проверку реестра оплаты.',
)
def check_payment_registry_view(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Проверять реестр можно только из формы.'
        )

        return redirect(
            'payment_registry'
        )

    from .models import PaymentRegistry
    from .payment_registry_services import check_payment_registry

    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
            created_by=request.user,
            status=PaymentRegistry.STATUS_DRAFT,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Черновик реестра не найден.'
        )

        return redirect(
            'payment_registry'
        )

    result = check_payment_registry(
        registry
    )

    if result['items_count'] == 0:

        messages.warning(
            request,
            f'Реестр №{registry.id} пуст. Сначала добавь счета.'
        )

        return redirect(
            'payment_registry'
        )

    if result['errors_count']:

        messages.warning(
            request,
            f'Реестр №{registry.id} не готов к выгрузке: ошибок {result["errors_count"]}.'
        )

        for error in result['errors'][:5]:

            messages.warning(
                request,
                f'Счёт #{error["invoice_id"]}: ' + '; '.join(error['messages'])
            )

    else:

        messages.success(
            request,
            f'Реестр №{registry.id} проверен: к выгрузке готово {result["ready_count"]} счетов.'
        )

    if result['warnings_count']:

        messages.info(
            request,
            f'Предупреждений: {result["warnings_count"]}.'
        )

    return redirect(
        'payment_registry'
    )


@login_required
@require_payment_registry_permission(
    user_can_export_payment_registry,
    'Нет прав на выгрузку реестра оплаты.',
)
def export_payment_registry_draft_excel(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Выгрузка реестра выполняется только из формы.'
        )

        return redirect(
            'payment_registry'
        )

    from decimal import Decimal
    from io import BytesIO

    from django.http import HttpResponse
    from django.utils import timezone

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    from .models import PaymentRegistry, PaymentRegistryItem
    from .payment_registry_services import (
        check_payment_registry,
        recalculate_payment_registry,
    )

    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
            created_by=request.user,
            status=PaymentRegistry.STATUS_DRAFT,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Черновик реестра не найден или уже выгружен.'
        )

        return redirect(
            'payment_registry'
        )

    check_result = check_payment_registry(
        registry
    )

    if check_result['items_count'] == 0:

        messages.warning(
            request,
            f'Реестр №{registry.id} пуст. Сначала добавь счета.'
        )

        return redirect(
            'payment_registry'
        )

    if check_result['errors_count']:

        messages.warning(
            request,
            f'Реестр №{registry.id} нельзя выгрузить: ошибок {check_result["errors_count"]}.'
        )

        return redirect(
            'payment_registry'
        )

    items = (
        registry.items
        .select_related(
            'invoice',
            'invoice__counterparty',
            'invoice__user',
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            'planned_payment_date',
            'invoice_id',
        )
    )

    wb = Workbook()
    ws = wb.active
    ws.title = f'Registry {registry.id}'

    headers = [
        '№ реестра',
        'ID счета',
        'Номер счета',
        'Контрагент',
        'ИНН',
        'КПП',
        'Банк',
        'Расчетный счет',
        'БИК',
        'Корр. счет',
        'Сумма',
        'Дата оплаты',
        'Назначение платежа',
        'Ответственный',
    ]

    ws.append(headers)

    header_fill = PatternFill(
        fill_type='solid',
        fgColor='1F2937',
    )

    for cell in ws[1]:
        cell.font = Font(
            bold=True,
            color='FFFFFF',
        )
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal='center',
            vertical='center',
        )

    for item in items:

        invoice = item.invoice
        counterparty = invoice.counterparty

        amount = item.amount or Decimal('0')
        payment_date = item.planned_payment_date or invoice.planned_payment_date

        purpose = (
            getattr(invoice, 'payment_purpose', '')
            or getattr(invoice, 'purpose', '')
            or getattr(invoice, 'description', '')
            or ''
        )

        ws.append(
            [
                registry.id,
                invoice.id,
                invoice.invoice_number or '',
                counterparty.name if counterparty else '',
                getattr(counterparty, 'inn', '') if counterparty else '',
                getattr(counterparty, 'kpp', '') if counterparty else '',
                getattr(counterparty, 'bank_name', '') if counterparty else '',
                getattr(counterparty, 'account_number', '') if counterparty else '',
                getattr(counterparty, 'bik', '') if counterparty else '',
                getattr(counterparty, 'correspondent_account', '') if counterparty else '',
                float(amount),
                payment_date.strftime('%d.%m.%Y') if payment_date else '',
                purpose,
                invoice.user.get_username() if invoice.user else '',
            ]
        )

    for column_cells in ws.columns:
        max_length = 0
        column_letter = get_column_letter(
            column_cells[0].column
        )

        for cell in column_cells:
            value = str(cell.value or '')
            max_length = max(
                max_length,
                len(value),
            )

        ws.column_dimensions[column_letter].width = min(
            max_length + 2,
            42,
        )

    ws.freeze_panes = 'A2'

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    now = timezone.now()

    registry.status = PaymentRegistry.STATUS_EXPORTED
    registry.exported_by = request.user
    registry.exported_at = now
    registry.save(
        update_fields=(
            'status',
            'exported_by',
            'exported_at',
        )
    )

    items.update(
        status=PaymentRegistryItem.STATUS_EXPORTED,
        exported_at=now,
    )

    recalculate_payment_registry(
        registry
    )

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

    response['Content-Disposition'] = (
        f'attachment; filename="payment_registry_{registry.id}.xlsx"'
    )

    return response


@login_required
@require_payment_registry_permission(
    user_can_export_payment_registry,
    'Нет прав на выгрузку реестра оплаты.',
)
def export_payment_registry_draft_1c(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Выгрузка реестра выполняется только из формы.'
        )

        return redirect(
            'payment_registry'
        )

    import csv
    from io import StringIO

    from django.http import HttpResponse
    from django.utils import timezone

    from .models import PaymentRegistry, PaymentRegistryItem
    from .payment_registry_services import (
        check_payment_registry,
        recalculate_payment_registry,
    )

    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
            created_by=request.user,
            status=PaymentRegistry.STATUS_DRAFT,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Черновик реестра не найден или уже выгружен.'
        )

        return redirect(
            'payment_registry'
        )

    check_result = check_payment_registry(
        registry
    )

    if check_result['items_count'] == 0:

        messages.warning(
            request,
            f'Реестр №{registry.id} пуст. Сначала добавь счета.'
        )

        return redirect(
            'payment_registry'
        )

    if check_result['errors_count']:

        messages.warning(
            request,
            f'Реестр №{registry.id} нельзя выгрузить: ошибок {check_result["errors_count"]}.'
        )

        return redirect(
            'payment_registry'
        )

    items = (
        registry.items
        .select_related(
            'invoice',
            'invoice__counterparty',
            'invoice__user',
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            'planned_payment_date',
            'invoice_id',
        )
    )

    buffer = StringIO()
    writer = csv.writer(
        buffer,
        delimiter=';',
        lineterminator='\n',
    )

    writer.writerow(
        [
            'RegistryID',
            'InvoiceID',
            'InvoiceNumber',
            'Counterparty',
            'INN',
            'KPP',
            'Bank',
            'BankAccount',
            'BIK',
            'CorrAccount',
            'Amount',
            'PaymentDate',
            'Purpose',
        ]
    )

    for item in items:

        invoice = item.invoice
        counterparty = invoice.counterparty
        payment_date = item.planned_payment_date or invoice.planned_payment_date

        purpose = (
            getattr(invoice, 'payment_purpose', '')
            or getattr(invoice, 'purpose', '')
            or getattr(invoice, 'description', '')
            or ''
        )

        writer.writerow(
            [
                registry.id,
                invoice.id,
                invoice.invoice_number or '',
                counterparty.name if counterparty else '',
                getattr(counterparty, 'inn', '') if counterparty else '',
                getattr(counterparty, 'kpp', '') if counterparty else '',
                getattr(counterparty, 'bank_name', '') if counterparty else '',
                getattr(counterparty, 'account_number', '') if counterparty else '',
                getattr(counterparty, 'bik', '') if counterparty else '',
                getattr(counterparty, 'correspondent_account', '') if counterparty else '',
                str(item.amount).replace('.', ','),
                payment_date.strftime('%d.%m.%Y') if payment_date else '',
                purpose,
            ]
        )

    now = timezone.now()

    registry.status = PaymentRegistry.STATUS_EXPORTED
    registry.exported_by = request.user
    registry.exported_at = now
    registry.save(
        update_fields=(
            'status',
            'exported_by',
            'exported_at',
        )
    )

    items.update(
        status=PaymentRegistryItem.STATUS_EXPORTED,
        exported_at=now,
    )

    recalculate_payment_registry(
        registry
    )

    content = '\ufeff' + buffer.getvalue()

    response = HttpResponse(
        content,
        content_type='text/plain; charset=utf-8',
    )

    response['Content-Disposition'] = (
        f'attachment; filename="payment_registry_{registry.id}_1c.txt"'
    )

    return response


@login_required
@require_payment_registry_permission(
    user_can_mark_payment_registry_paid,
    'Нет прав на отметку реестра оплаченным.',
)
def mark_payment_registry_paid(request, registry_id):
    registry = get_object_or_404(
        PaymentRegistry,
        id=registry_id
    )

    if (
        not request.user.is_staff
        and not request.user.is_superuser
        and registry.created_by_id != request.user.id
    ):
        raise PermissionDenied

    if request.method != "POST":
        return redirect(
            "payment_registry_detail",
            registry_id=registry.id
        )

    try:
        result = mark_payment_registry_as_paid(
            registry,
            user=request.user
        )
    except ValueError as error:
        messages.error(
            request,
            str(error)
        )

        return redirect(
            "payment_registry_detail",
            registry_id=registry.id
        )

    messages.success(
        request,
        (
            "Реестр отмечен оплаченным. "
            f"Создано оплат: {result.get('paid_count', 0)}. "
            f"Пропущено закрытых счетов: {result.get('skipped_count', 0)}."
        )
    )

    return redirect(
        "payment_registry_detail",
        registry_id=registry.id
    )

@login_required
@require_payment_registry_permission(
    user_can_cancel_payment_registry,
    'Нет прав на отмену реестра оплаты.',
)
def cancel_payment_registry_view(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Отменить реестр можно только из формы.'
        )

        return redirect(
            'payment_registry_detail',
            registry_id=registry_id,
        )

    from .models import PaymentRegistry
    from .payment_registry_services import cancel_payment_registry

    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Реестр оплаты не найден.'
        )

        return redirect(
            'payment_registry_history'
        )

    if not request.user.is_staff and registry.created_by_id != request.user.id:

        messages.warning(
            request,
            'Нет доступа к этому реестру.'
        )

        return redirect(
            'payment_registry_history'
        )

    reason = request.POST.get(
        'reason',
        ''
    ).strip()

    cancelled = cancel_payment_registry(
        registry,
        user=request.user,
        reason=reason,
    )

    if not cancelled:

        messages.warning(
            request,
            'Можно отменить только черновик или проверенный реестр.'
        )

        return redirect(
            'payment_registry_detail',
            registry_id=registry.id,
        )

    messages.success(
        request,
        f'Реестр оплаты №{registry.id} отменён.'
    )

    return redirect(
        'payment_registry_detail',
        registry_id=registry.id,
    )


@login_required
def payment_registry_detail(request, registry_id):

    from .models import PaymentRegistry, PaymentRegistryItem
    from .payment_registry_services import check_payment_registry

    registry = (
        PaymentRegistry.objects
        .select_related(
            'created_by',
            'checked_by',
            'exported_by',
        )
        .filter(
            id=registry_id,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Реестр оплаты не найден.'
        )

        return redirect(
            'payment_registry_history'
        )

    if not request.user.is_staff and registry.created_by_id != request.user.id:

        messages.warning(
            request,
            'Нет доступа к этому реестру.'
        )

        return redirect(
            'payment_registry_history'
        )

    registry_items = (
        registry.items
        .select_related(
            'invoice',
            'invoice__counterparty',
            'invoice__user',
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            'planned_payment_date',
            'invoice_id',
        )
    )

    check_result = None

    if registry.status == PaymentRegistry.STATUS_DRAFT:

        check_result = check_payment_registry(
            registry
        )

    return render(
        request,
        'invoices/payment_registry_detail.html',
        {
            'page_title': f'Реестр оплаты №{registry.id}',
            'registry': registry,
            'registry_items': registry_items,
            'check_result': check_result,
        }
    )


@login_required
def payment_registry_history(request):

    from django.core.paginator import Paginator
    from django.db.models import Sum, Q

    from .models import PaymentRegistry

    status_filter = request.GET.get(
        'status',
        ''
    ).strip()

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    registries = (
        PaymentRegistry.objects
        .select_related(
            'created_by',
            'checked_by',
            'exported_by',
        )
        .all()
        .order_by(
            '-created_at',
        )
    )

    if not request.user.is_staff:

        registries = registries.filter(
            created_by=request.user,
        )

    if status_filter:

        registries = registries.filter(
            status=status_filter,
        )

    if search_query:

        registries = registries.filter(
            Q(title__icontains=search_query)
            | Q(comment__icontains=search_query)
            | Q(created_by__username__icontains=search_query)
            | Q(exported_by__username__icontains=search_query)
        )

    total_registries = registries.count()

    total_amount = (
        registries.aggregate(
            total=Sum('total_amount')
        ).get('total')
        or 0
    )

    draft_count = registries.filter(
        status=PaymentRegistry.STATUS_DRAFT,
    ).count()

    exported_count = registries.filter(
        status=PaymentRegistry.STATUS_EXPORTED,
    ).count()

    paid_count = registries.filter(
        status=PaymentRegistry.STATUS_PAID,
    ).count()

    paginator = Paginator(
        registries,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get('page')
    )

    return render(
        request,
        'invoices/payment_registry_history.html',
        {
            'page_title': 'История реестров оплаты',
            'page_obj': page_obj,
            'registries': page_obj.object_list,
            'status_filter': status_filter,
            'search_query': search_query,
            'status_choices': PaymentRegistry.STATUS_CHOICES,
            'total_registries': total_registries,
            'total_amount': total_amount,
            'draft_count': draft_count,
            'exported_count': exported_count,
            'paid_count': paid_count,
        }
    )


@login_required
def payment_registry(request):

    selected_status = request.GET.get(
        'status',
        Invoice.STATUS_APPROVED
    )

    selected_counterparty = request.GET.get(
        'counterparty',
        ''
    )

    registry_payment_status_filter = request.GET.get(
        'payment_status',
        ''
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    date_from = request.GET.get(
        'date_from',
        ''
    ).strip()

    date_to = request.GET.get(
        'date_to',
        ''
    ).strip()

    from .models import PaymentRegistry, PaymentRegistryItem
    from .payment_registry_services import ACTIVE_REGISTRY_STATUSES, check_payment_registry

    from .payment_registry_services import (
        get_or_create_draft_payment_registry,
    )

    draft_registry, draft_registry_created = get_or_create_draft_payment_registry(request.user)

    draft_registry_items = PaymentRegistryItem.objects.none()
    draft_registry_check_result = None

    if draft_registry:

        draft_registry_items = (
            draft_registry.items
            .select_related(
                'invoice',
                'invoice__counterparty',
                'invoice__user',
            )
            .exclude(
                status=PaymentRegistryItem.STATUS_CANCELLED
            )
            .order_by(
                'planned_payment_date',
                'invoice_id',
            )
        )

        draft_registry_check_result = check_payment_registry(
            draft_registry
        )

    active_registry_invoice_ids = (
        PaymentRegistryItem.objects
        .filter(
            registry__status__in=ACTIVE_REGISTRY_STATUSES,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .values_list(
            'invoice_id',
            flat=True,
        )
    )

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .exclude(
            status=Invoice.STATUS_PAID
        )
        .exclude(
            id__in=active_registry_invoice_ids
        )
    )

    if selected_status and selected_status != 'all':

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_counterparty:

        invoices = invoices.filter(
            counterparty_id=selected_counterparty
        )

    invoices = apply_payment_status_filter(
        invoices,
        registry_payment_status_filter
    )

    if search_query:

        invoices = invoices.filter(
            Q(title__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
        )

    if date_from:

        invoices = invoices.filter(
            planned_payment_date__gte=date_from
        )

    if date_to:

        invoices = invoices.filter(
            planned_payment_date__lte=date_to
        )

    invoices = apply_positive_payment_balance_filter(
        invoices
    )

    total_amount = (
        invoices.aggregate(
            total=Sum(
                'amount'
            )
        ).get(
            'total'
        )
        or 0
    )

    counterparties = (
        Counterparty.objects
        .filter(
            invoices__isnull=False
        )
        .distinct()
        .order_by(
            'name'
        )
    )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
    )

    # OCR_REGISTRY_SUMMARY_CONTEXT_V3
    ocr_registry_draft_items = list(draft_registry_items or [])
    draft_registry_items = ocr_registry_draft_items

    ocr_registry_invoice_map = {}

    for item in ocr_registry_draft_items:
        if item.invoice_id:
            ocr_registry_invoice_map[item.invoice_id] = item.invoice

    for invoice in list(invoices or []):
        if invoice.id:
            ocr_registry_invoice_map[invoice.id] = invoice

    ocr_registry_invoices = list(ocr_registry_invoice_map.values())
    ocr_registry_items_count = len(ocr_registry_invoices)
    ocr_registry_ready_count = sum(
        1
        for invoice in ocr_registry_invoices
        if invoice.amount_verified
    )
    ocr_registry_errors_count = sum(
        1
        for invoice in ocr_registry_invoices
        if not invoice.amount_verified
    )

    return render(
        request,
        'invoices/payment_registry.html',
        {
            'invoices': invoices,
            'counterparties': counterparties,
            'total_amount': total_amount,
            'selected_status': selected_status,
            'selected_counterparty': selected_counterparty,
            'registry_payment_status_filter': registry_payment_status_filter,
            'payment_status_choices': PAYMENT_STATUS_FILTER_CHOICES,
            'search_query': search_query,
            'date_from': date_from,
            'date_to': date_to,
            'status_choices': Invoice.STATUS_CHOICES,
            'draft_registry': draft_registry,
            'draft_registry_items': draft_registry_items,
            "ocr_registry_items_count": ocr_registry_items_count,
            "ocr_registry_ready_count": ocr_registry_ready_count,
            "ocr_registry_errors_count": ocr_registry_errors_count,
            'draft_registry_items_count': draft_registry.items_count if draft_registry else 0,
            'draft_registry_total_amount': draft_registry.total_amount if draft_registry else 0,
            'draft_registry_check_result': draft_registry_check_result,
        }
    )


@login_required
@require_payment_registry_permission(
    user_can_export_payment_registry,
    'Нет прав на выгрузку реестра оплаты.',
)
def export_payment_registry_excel(request):

    selected_status = request.GET.get(
        'status',
        Invoice.STATUS_APPROVED
    )

    selected_counterparty = request.GET.get(
        'counterparty',
        ''
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    date_from = request.GET.get(
        'date_from',
        ''
    ).strip()

    date_to = request.GET.get(
        'date_to',
        ''
    ).strip()

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .exclude(
            status=Invoice.STATUS_PAID
        )
    )

    if selected_status and selected_status != 'all':

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_counterparty:

        invoices = invoices.filter(
            counterparty_id=selected_counterparty
        )

    if search_query:

        invoices = invoices.filter(
            Q(title__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
        )

    if date_from:

        invoices = invoices.filter(
            planned_payment_date__gte=date_from
        )

    if date_to:

        invoices = invoices.filter(
            planned_payment_date__lte=date_to
        )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
    )

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = 'Реестр оплаты'

    headers = [
        'ID',
        'Контрагент',
        'ИНН',
        'КПП',
        'Номер счета',
        'Дата счета',
        'Сумма',
        'Плановая дата оплаты',
        'Приоритет',
        'Статус',
        'Назначение платежа',
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
            vertical='center'
        )

    total_amount = Decimal(
        '0.00'
    )

    for invoice in invoices:

        if invoice.counterparty:

            counterparty_name = invoice.counterparty.name or ''
            inn = invoice.counterparty.inn or ''
            kpp = invoice.counterparty.kpp or ''

        else:

            counterparty_name = invoice.vendor or ''
            inn = ''
            kpp = ''

        amount = invoice.amount or Decimal(
            '0.00'
        )

        total_amount += amount

        if invoice.invoice_number:

            payment_purpose = (
                f'Оплата по счету №{invoice.invoice_number}'
            )

            if invoice.invoice_date:

                payment_purpose += (
                    f' от {invoice.invoice_date}'
                )

        else:

            payment_purpose = (
                f'Оплата по счету ID {invoice.id}'
            )

        sheet.append(
            [
                invoice.id,
                counterparty_name,
                inn,
                kpp,
                invoice.invoice_number or '',
                invoice.invoice_date or '',
                amount,
                (
                    invoice.planned_payment_date.strftime(
                        '%d.%m.%Y'
                    )
                    if invoice.planned_payment_date
                    else ''
                ),
                invoice.payment_priority,
                invoice.get_status_display(),
                payment_purpose,
            ]
        )

    total_row = sheet.max_row + 2

    sheet.cell(
        row=total_row,
        column=6,
        value='Итого:'
    )

    sheet.cell(
        row=total_row,
        column=7,
        value=total_amount
    )

    sheet.cell(
        row=total_row,
        column=6
    ).font = Font(
        bold=True
    )

    sheet.cell(
        row=total_row,
        column=7
    ).font = Font(
        bold=True
    )

    for row in sheet.iter_rows():

        for cell in row:

            cell.alignment = Alignment(
                vertical='top',
                wrap_text=True
            )

    column_widths = {
        'A': 8,
        'B': 36,
        'C': 16,
        'D': 14,
        'E': 18,
        'F': 16,
        'G': 16,
        'H': 20,
        'I': 12,
        'J': 18,
        'K': 48,
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
            column=7
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
        'attachment; filename="payment_registry.xlsx"'
    )

    workbook.save(
        response
    )

    return response


@login_required
@require_payment_registry_permission(
    user_can_export_payment_registry,
    'Нет прав на выгрузку реестра оплаты.',
)
def export_payment_registry_1c(request):

    company = CompanyRequisites.objects.first()

    if not company:

        messages.error(
            request,
            'Сначала заполните реквизиты организации в админке.'
        )

        return redirect(
            'payment_registry'
        )

    selected_status = request.GET.get(
        'status',
        Invoice.STATUS_APPROVED
    )

    selected_counterparty = request.GET.get(
        'counterparty',
        ''
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    date_from = request.GET.get(
        'date_from',
        ''
    ).strip()

    date_to = request.GET.get(
        'date_to',
        ''
    ).strip()

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .exclude(
            status=Invoice.STATUS_PAID
        )
    )

    if selected_status and selected_status != 'all':

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_counterparty:

        invoices = invoices.filter(
            counterparty_id=selected_counterparty
        )

    if search_query:

        invoices = invoices.filter(
            Q(title__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
        )

    if date_from:

        invoices = invoices.filter(
            planned_payment_date__gte=date_from
        )

    if date_to:

        invoices = invoices.filter(
            planned_payment_date__lte=date_to
        )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
    )

    missing_requisites = []

    for invoice in invoices:

        counterparty = invoice.counterparty

        if not counterparty:

            missing_requisites.append(
                f'Счет #{invoice.id}: контрагент не найден'
            )

            continue

        required_values = [
            counterparty.inn,
            counterparty.bank_name,
            counterparty.bik,
            counterparty.account_number,
        ]

        if any(
            not value
            for value in required_values
        ):

            missing_requisites.append(
                f'Счет #{invoice.id}: {counterparty.name}'
            )

    if missing_requisites:

        messages.error(
            request,
            (
                'Выгрузка 1С TXT остановлена. '
                'Есть контрагенты без обязательных платежных реквизитов.'
            )
        )

        return redirect(
            'counterparties_missing_requisites'
        )

    def clean_value(value):

        if value is None:

            return ''

        value = str(value)

        value = value.replace(
            '\r',
            ' '
        )

        value = value.replace(
            '\n',
            ' '
        )

        value = value.strip()

        return value

    def format_date(value):

        if value:

            return value.strftime(
                '%d.%m.%Y'
            )

        return date.today().strftime(
            '%d.%m.%Y'
        )

    def format_amount(value):

        if not value:

            return '0.00'

        return f'{value:.2f}'

    created_at = datetime.now()

    lines = []

    lines.append(
        '1CClientBankExchange'
    )

    lines.append(
        'ВерсияФормата=1.03'
    )

    lines.append(
        'Кодировка=Windows'
    )

    lines.append(
        'Отправитель=Project Zarya'
    )

    lines.append(
        'Получатель=1С'
    )

    lines.append(
        f'ДатаСоздания={created_at.strftime("%d.%m.%Y")}'
    )

    lines.append(
        f'ВремяСоздания={created_at.strftime("%H:%M:%S")}'
    )

    lines.append(
        f'РасчСчет={clean_value(company.account_number)}'
    )

    for invoice in invoices:

        if not invoice.counterparty:

            continue

        counterparty = invoice.counterparty

        amount = invoice.amount or 0

        payment_date = invoice.planned_payment_date or date.today()

        if invoice.invoice_number:

            payment_purpose = (
                f'Оплата по счету №{invoice.invoice_number}'
            )

            if invoice.invoice_date:

                payment_purpose += (
                    f' от {invoice.invoice_date}'
                )

        else:

            payment_purpose = (
                f'Оплата по счету ID {invoice.id}'
            )

        lines.append(
            'СекцияДокумент=Платежное поручение'
        )

        lines.append(
            f'Номер={invoice.id}'
        )

        lines.append(
            f'Дата={format_date(payment_date)}'
        )

        lines.append(
            f'Сумма={format_amount(amount)}'
        )

        lines.append(
            f'Плательщик={clean_value(company.name)}'
        )

        lines.append(
            f'ПлательщикИНН={clean_value(company.inn)}'
        )

        lines.append(
            f'ПлательщикКПП={clean_value(company.kpp)}'
        )

        lines.append(
            f'ПлательщикСчет={clean_value(company.account_number)}'
        )

        lines.append(
            f'ПлательщикБанк1={clean_value(company.bank_name)}'
        )

        lines.append(
            f'ПлательщикБИК={clean_value(company.bik)}'
        )

        lines.append(
            f'ПлательщикКорсчет={clean_value(company.correspondent_account)}'
        )

        lines.append(
            f'Получатель={clean_value(counterparty.name)}'
        )

        lines.append(
            f'ПолучательИНН={clean_value(counterparty.inn)}'
        )

        lines.append(
            f'ПолучательКПП={clean_value(counterparty.kpp)}'
        )

        lines.append(
            f'ПолучательСчет={clean_value(counterparty.account_number)}'
        )

        lines.append(
            f'ПолучательБанк1={clean_value(counterparty.bank_name)}'
        )

        lines.append(
            f'ПолучательБИК={clean_value(counterparty.bik)}'
        )

        lines.append(
            f'ПолучательКорсчет={clean_value(counterparty.correspondent_account)}'
        )

        lines.append(
            'ВидПлатежа=Электронно'
        )

        lines.append(
            'ВидОплаты=01'
        )

        lines.append(
            'Очередность=5'
        )

        lines.append(
            f'НазначениеПлатежа={clean_value(payment_purpose)}'
        )

        lines.append(
            'КонецДокумента'
        )

    lines.append(
        'КонецФайла'
    )

    content = '\r\n'.join(
        lines
    )

    response = HttpResponse(
        content.encode(
            'cp1251',
            errors='replace'
        ),
        content_type='text/plain; charset=windows-1251'
    )

    response[
        'Content-Disposition'
    ] = (
        'attachment; filename="payment_registry_1c.txt"'
    )

    return response


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
