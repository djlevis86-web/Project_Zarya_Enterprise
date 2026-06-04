from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import (
    get_dashboard_stats,
    get_monthly_stats
)


@login_required
def reports_dashboard(request):

    stats = get_dashboard_stats(
        request.user
    )

    monthly_stats = get_monthly_stats(
        request.user
    )

    labels = []
    values = []

    for item in monthly_stats:

        labels.append(
            item['month'].strftime('%b %Y')
        )

        values.append(
            float(item['total'])
        )

    return render(
        request,
        'reports/dashboard.html',
        {
            'stats': stats,
            'labels': labels,
            'values': values,
        }
    )