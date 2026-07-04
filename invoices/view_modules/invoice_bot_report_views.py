from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from ..bot_report_services import get_invoice_bot_report_items
from ..payment_registry_permissions import (
    require_payment_registry_permission,
    user_can_manage_payment_registry,
)


@login_required
@require_payment_registry_permission(
    user_can_manage_payment_registry,
    "Нет прав на просмотр отчёта бота.",
)
def invoice_bot_report_detail(request, category):
    category_data, invoice_items = get_invoice_bot_report_items(
        category
    )

    if category_data is None:
        raise Http404(
            "Категория отчёта бота не найдена."
        )

    paginator = Paginator(
        invoice_items,
        50,
    )

    page_obj = paginator.get_page(
        request.GET.get(
            "page"
        )
    )

    return render(
        request,
        "invoices/invoice_bot_report_detail.html",
        {
            "category": category,
            "category_data": category_data,
            "page_obj": page_obj,
            "items_count": len(
                invoice_items
            ),
        }
    )
