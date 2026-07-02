import hashlib
import traceback
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from audit.models import AuditLog
from audit.services import log_action
from ..forms import UploadInvoiceForm
from ..log_service import create_invoice_log
from ..counterparty_service import get_or_create_counterparty_from_invoice
from ..models import Invoice, InvoiceUploadBatch, OCRJob
from ..ocr_processing_service import apply_ocr_identity_to_invoice, get_duplicate_invoice_by_ocr_identity, read_and_parse_invoice_file
from ..ocr_verification_service import apply_ocr_amount_to_invoice


INLINE_OCR_MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024


def enqueue_upload_ocr_job(invoice, user):
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
        return existing_job, False

    job = OCRJob.objects.create(
        invoice=invoice,
        user=user,
        status=OCRJob.STATUS_PENDING,
        source='upload',
    )

    create_invoice_log(
        invoice,
        user,
        'OCR поставлен в очередь автоматически после загрузки'
    )

    return job, True


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


def match_counterparty_after_upload_ocr(invoice, user):
    try:
        invoice.counterparty = None

        counterparty = get_or_create_counterparty_from_invoice(
            invoice
        )

        invoice.counterparty = counterparty

        invoice.save(
            update_fields=[
                "counterparty",
                "counterparty_match_status",
                "counterparty_match_comment",
            ]
        )

        if counterparty:
            create_invoice_log(
                invoice,
                user,
                f"Контрагент сопоставлен после OCR при загрузке: {counterparty.name}"
            )

    except Exception as match_error:
        create_invoice_log(
            invoice,
            user,
            f"Ошибка сопоставления контрагента после OCR при загрузке: {match_error}"
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

        form = UploadInvoiceForm(
            request.POST,
            request.FILES
        )

        if not form.is_valid():

            messages.error(
                request,
                'Загрузка не выполнена. Проверьте ошибки ниже.'
            )

            for field_name, errors in form.errors.items():
                field = form.fields.get(
                    field_name
                )

                label = field.label if field else field_name

                for error in errors:
                    messages.error(
                        request,
                        f'{label}: {error}'
                    )

            return render_upload_invoice_form(
                request,
                form
            )

        files = form.cleaned_data.get(
            'files'
        ) or request.FILES.getlist(
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
                document_type=(
                    form.cleaned_data.get(
                        'document_type'
                    )
                    or Invoice.DOCUMENT_TYPE_INVOICE
                ),
                title=(
                    form.cleaned_data.get(
                        'title'
                    )
                    or uploaded_file.name
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

            if (
                len(files) > 1
                or getattr(uploaded_file, 'size', 0) > INLINE_OCR_MAX_FILE_SIZE_BYTES
            ):
                ocr_job, ocr_job_created = enqueue_upload_ocr_job(
                    invoice,
                    request.user,
                )

                invoice.ocr_comment = (
                    "OCR отложен: пакетная загрузка или большой файл. "
                    "Счет сохранен и доступен в разделе Счета. "
                    f"OCR поставлен в очередь #{ocr_job.id}."
                )
                invoice.save(
                    update_fields=[
                        'ocr_comment',
                        'updated_at',
                    ]
                )

                create_invoice_log(
                    invoice,
                    request.user,
                    "Счет загружен без inline OCR: OCR поставлен в очередь"
                )

                if ocr_job_created:
                    log_action(
                        request=request,
                        action=AuditLog.ACTION_UPDATE,
                        obj=invoice,
                        message=f"OCR задача #{ocr_job.id} создана автоматически после загрузки.",
                    )

                created_count += 1
                continue

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

                amount_warning = apply_ocr_amount_to_invoice(
                    invoice,
                    parsed.get(
                        'amount'
                    ),
                    prefill_amount_from_ocr=True,
                )

                if amount_warning:
                    invoice.ocr_comment = (
                        f"{invoice.ocr_comment or ''} "
                        f"{amount_warning}"
                    ).strip()

                match_counterparty_after_upload_ocr(
                    invoice,
                    request.user,
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

        if created_count > 0:
            messages.success(
                request,
                f"Загружено счетов: {created_count}. "
                "Если OCR был отложен, счета уже доступны в разделе Счета."
            )

        if duplicate_files:
            messages.warning(
                request,
                f"Дубликаты не загружены: {len(duplicate_files)}."
            )

        if skipped_files:
            messages.warning(
                request,
                f"Файлы с неподдерживаемым форматом пропущены: {len(skipped_files)}."
            )

        if created_count == 0:
            messages.warning(
                request,
                "Новые счета не созданы. Проверьте список дубликатов и пропущенных файлов."
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

    form = UploadInvoiceForm()

    return render_upload_invoice_form(
        request,
        form
    )

