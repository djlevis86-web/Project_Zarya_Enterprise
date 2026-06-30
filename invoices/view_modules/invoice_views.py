import hashlib
import traceback
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from audit.models import AuditLog
from audit.services import log_action

from ..comment_forms import InvoiceCommentForm
from ..comment_models import InvoiceComment
from ..forms import (
    InvoiceEditForm,
    InvoiceForm,
    InvoicePaymentForm,
)
from ..log_service import create_invoice_log
from ..models import Invoice, InvoicePayment, InvoiceUploadBatch
from ..ocr_processing_service import (
    apply_ocr_identity_to_invoice,
    get_duplicate_invoice_by_ocr_identity,
    read_and_parse_invoice_file,
)
from ..ocr_verification_service import (
    apply_ocr_amount_to_invoice,
    sync_invoice_amount_verification,
)
from ..payment_registry_services import get_active_registry_items_for_invoice
from ..payment_services import get_invoice_payment_summary
from .payment_registry_helpers import (
    PAYMENT_STATUS_FILTER_CHOICES,
    apply_payment_status_filter,
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

from .invoice_upload_batch_views import (
    upload_batch_detail,
    upload_batches,
)

from .invoice_upload_result_views import (
    upload_result,
)

from .invoice_status_comment_views import (
    add_comment,
    change_invoice_status,
)

from .invoice_detail_views import (
    invoice_detail,
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
