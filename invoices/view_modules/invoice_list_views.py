from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from ..models import Invoice
from .payment_registry_helpers import PAYMENT_STATUS_FILTER_CHOICES, apply_payment_status_filter


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
