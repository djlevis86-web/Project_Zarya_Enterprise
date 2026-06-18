from datetime import date, datetime
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

                if invoice.invoice_number:

                    exists_invoice = (
                        Invoice.objects
                        .filter(
                            invoice_number=invoice.invoice_number
                        )
                        .exclude(
                            id=invoice.id
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
                            }
                        )

                        continue

                invoice.invoice_date = parsed.get(
                    'invoice_date'
                )

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

        number_warning = ''

        if parsed_invoice_number:

            duplicate_invoice = (
                Invoice.objects
                .filter(
                    invoice_number=parsed_invoice_number
                )
                .exclude(
                    id=invoice.id
                )
                .first()
            )

            if duplicate_invoice:

                number_warning = (
                    f'OCR нашел номер {parsed_invoice_number}, '
                    f'но такой номер уже есть у счета #{duplicate_invoice.id}. '
                    'Номер текущего счета не изменен.'
                )

            else:

                invoice.invoice_number = parsed_invoice_number

        else:

            invoice.invoice_number = None

        invoice.invoice_date = parsed.get(
            'invoice_date'
        )

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

        number_warning = ''

        if parsed_invoice_number:

            duplicate_invoice = (
                Invoice.objects
                .filter(
                    invoice_number=parsed_invoice_number
                )
                .exclude(
                    id=invoice.id
                )
                .first()
            )

            if duplicate_invoice:

                number_warning = (
                    f'OCR нашел номер {parsed_invoice_number}, '
                    f'но такой номер уже есть у счета #{duplicate_invoice.id}. '
                    'Номер текущего счета не изменен.'
                )

            else:

                invoice.invoice_number = parsed_invoice_number

        else:

            invoice.invoice_number = None

        invoice.invoice_date = parsed.get(
            'invoice_date'
        )

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

    invoice.status = status

    invoice.save()

    create_invoice_log(
        invoice,
        request.user,
        f'Статус изменен на "{invoice.get_status_display()}"'
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

    total_count = base_invoices.count()

    today_count = base_invoices.filter(
        planned_payment_date=today
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

    elif filter_type == 'overdue':

        invoices = invoices.filter(
            planned_payment_date__lt=today
        )

    elif filter_type == 'no_date':

        invoices = invoices.filter(
            planned_payment_date__isnull=True
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
            'filter_type': filter_type,
            'total_count': total_count,
            'today_count': today_count,
            'overdue_count': overdue_count,
            'no_date_count': no_date_count,
            'total_amount': total_amount,
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

    return render(
        request,
        'invoices/payment_registry.html',
        {
            'invoices': invoices,
            'counterparties': counterparties,
            'total_amount': total_amount,
            'selected_status': selected_status,
            'selected_counterparty': selected_counterparty,
            'search_query': search_query,
            'date_from': date_from,
            'date_to': date_to,
            'status_choices': Invoice.STATUS_CHOICES,
        }
    )


@login_required
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

        amount = invoice.amount or invoice.ocr_amount or 0

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
