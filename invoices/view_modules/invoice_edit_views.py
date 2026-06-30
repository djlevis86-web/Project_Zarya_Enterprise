from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from ..forms import InvoiceEditForm
from ..log_service import create_invoice_log
from ..models import Invoice
from ..ocr_verification_service import sync_invoice_amount_verification
from ..payment_registry_services import get_active_registry_items_for_invoice


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
