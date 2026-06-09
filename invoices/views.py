from django.shortcuts import (
render,
redirect,
get_object_or_404
)

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from ocr.models import OCRJob
from ocr.tasks import process_invoice_ocr

from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Count

import hashlib

from .models import Invoice
from .forms import (
    InvoiceForm,
    InvoiceEditForm
)

from .log_service import create_invoice_log

from ocr.services import (
extract_text_from_pdf,
extract_text_from_image,
parse_invoice_data
)

from .comment_models import InvoiceComment
from .comment_forms import InvoiceCommentForm

@login_required
def invoice_list(request):

    User = get_user_model()

    invoices = Invoice.objects.select_related(
        'user'
    ).all()

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

            Q(title__icontains=search) |
            Q(original_filename__icontains=search) |
            Q(description__icontains=search) |
            Q(vendor__icontains=search) |
            Q(invoice_number__icontains=search) |
            Q(ocr_text__icontains=search) |
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

    invoices = invoices.order_by(sort)

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

        print('=' * 50)
        print('POST RECEIVED')
        print('POST DATA:', request.POST)
        print('FILES:', request.FILES)
        print('=' * 50)

        form = InvoiceForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            files = request.FILES.getlist('files')

            if not files:
                messages.error(
                    request,
                    'Выберите хотя бы один файл.'
                )

                return render(
                    request,
                    'invoices/upload_invoice.html',
                    {
                        'form': form
                    }
                )

            created_count = 0

            duplicate_files = []

            allowed_extensions = (
                '.pdf',
                '.jpg',
                '.jpeg',
                '.png'
            )

            for uploaded_file in files:

                uploaded_file.seek(0)

                file_hash = hashlib.md5(
                    uploaded_file.read()
                ).hexdigest()

                uploaded_file.seek(0)

                duplicate_found = False

                invoices_for_check = Invoice.objects.only(
                    'id',
                    'file'
                )

                for old_invoice in invoices_for_check:

                    try:

                        if not old_invoice.file:
                            continue

                        old_invoice.file.open('rb')

                        old_hash = hashlib.md5(
                            old_invoice.file.read()
                        ).hexdigest()

                        old_invoice.file.close()

                        if old_hash == file_hash:

                            duplicate_found = True

                            duplicate_files.append(
                                uploaded_file.name
                            )

                            break

                    except Exception:
                        pass

                if duplicate_found:
                    continue

                filename = uploaded_file.name.lower()

                if not filename.endswith(
                    allowed_extensions
                ):
                    continue

                print(
                    'PROCESS FILE:',
                    uploaded_file.name
                )

                invoice = Invoice()

                invoice.user = request.user

                invoice.title = form.cleaned_data[
                    'title'
                ]

                invoice.description = form.cleaned_data[
                    'description'
                ]

                invoice.amount = form.cleaned_data[
                    'amount'
                ]

                invoice.file = uploaded_file

                invoice.original_filename = (
                    uploaded_file.name
                )

                invoice.status = Invoice.STATUS_NEW

                invoice.save()

                job = OCRJob.objects.create(
                invoice_id=invoice.id,
                file_path=invoice.file.path
                )

                process_invoice_ocr.delay(
                    job.id
                )

                created_count += 1

            request.session[
                'uploaded_count'
            ] = created_count

            request.session[
                'duplicate_files'
            ] = duplicate_files

            return redirect(
                'upload_result'
            )

        else:

            print('=' * 50)
            print('FORM ERRORS')
            print(form.errors)
            print('=' * 50)

    else:

        form = InvoiceForm()

    return render(
        request,
        'invoices/upload_invoice.html',
        {
            'form': form
        }
    )

@login_required
def invoice_detail(
    request,
    invoice_id
):


    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if (
        not request.user.is_staff
        and invoice.user != request.user
    ):
        raise PermissionDenied

    comments = InvoiceComment.objects.filter(
        invoice=invoice
    ).select_related(
        'user'
    ).order_by(
        '-created_at'
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


@staff_member_required
def change_invoice_status(
    request,
    invoice_id,
    status
):

    user_filter = request.GET.get(
        'user',
        ''
    )

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
def add_comment(
    request,
    invoice_id
):


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
def edit_invoice(
    request,
    invoice_id
):

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
            'form': form
        }
    )

@login_required
def upload_result(request):

    uploaded = request.session.get(
        'uploaded_count',
        0
    )

    duplicates = request.session.get(
        'duplicate_files',
        []
    )

    request.session.pop(
        'uploaded_count',
        None
    )

    request.session.pop(
        'duplicate_files',
        None
    )

    return render(
        request,
        'invoices/upload_result.html',
        {
            'uploaded_count': uploaded,
            'duplicates': duplicates,
        }
    )