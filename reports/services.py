from django.db.models import Sum
from django.db.models.functions import TruncMonth

from invoices.models import Invoice


def get_dashboard_stats(user):

    invoices = Invoice.objects.all()

    if user.role != 'ADMIN':
        invoices = invoices.filter(user=user)

    total_invoices = invoices.count()

    total_amount = invoices.aggregate(
        Sum('amount')
    )['amount__sum'] or 0

    approved_count = invoices.filter(
        status='approved'
    ).count()

    rejected_count = invoices.filter(
        status='rejected'
    ).count()

    processing_count = invoices.filter(
        status='processing'
    ).count()

    return {
        'total_invoices': total_invoices,
        'total_amount': total_amount,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'processing_count': processing_count,
    }


def get_monthly_stats(user):

    invoices = Invoice.objects.all()

    if user.role != 'ADMIN':
        invoices = invoices.filter(user=user)

    monthly = (
        invoices
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    return monthly