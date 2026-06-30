from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from users.permissions import require_user_permission, user_can_process_invoices

from ..forms import InvoicePaymentForm
from ..log_service import create_invoice_log
from ..models import Invoice, InvoicePayment
from ..payment_services import create_invoice_payment, get_invoice_payment_summary


@login_required
@require_user_permission(user_can_process_invoices, 'Нет прав на отмену оплаты счета.')
def cancel_invoice_payment(request, payment_id):
    from ..models import InvoicePayment
    from ..payment_services import get_invoice_payment_summary

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
@require_user_permission(user_can_process_invoices, 'Нет прав на добавление оплаты счета.')
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
