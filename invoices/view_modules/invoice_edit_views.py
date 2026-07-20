from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from ..forms import InvoiceEditForm
from ..log_service import create_invoice_log
from ..models import Invoice
from ..ocr_verification_service import sync_invoice_amount_verification
from ..payment_registry_services import get_active_registry_items_for_invoice


def _redirect_after_quick_update(request):
    next_url = request.POST.get(
        'next'
    ) or request.META.get(
        'HTTP_REFERER'
    )

    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={
            request.get_host(),
        }
    ):
        return redirect(
            next_url
        )

    return redirect(
        'invoice_list'
    )


@staff_member_required
@require_POST
def quick_update_invoice(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        is_deleted=False,
    )

    status_choices = dict(
        Invoice.STATUS_CHOICES
    )

    new_status = request.POST.get(
        'status',
        ''
    )

    planned_payment_date_raw = request.POST.get(
        'planned_payment_date',
        ''
    )

    if new_status not in status_choices:
        messages.error(
            request,
            'Некорректный статус документа.'
        )

        return _redirect_after_quick_update(
            request
        )

    if not planned_payment_date_raw:
        messages.error(
            request,
            'Укажите плановую дату оплаты.'
        )

        return _redirect_after_quick_update(
            request
        )

    new_planned_payment_date = parse_date(
        planned_payment_date_raw
    )

    if not new_planned_payment_date:
        messages.error(
            request,
            'Введите корректную плановую дату оплаты.'
        )

        return _redirect_after_quick_update(
            request
        )

    old_status = invoice.status
    old_planned_payment_date = invoice.planned_payment_date

    changed_fields = []

    if old_status != new_status:
        invoice.status = new_status
        changed_fields.append(
            'status'
        )

    if old_planned_payment_date != new_planned_payment_date:
        invoice.planned_payment_date = new_planned_payment_date
        changed_fields.append(
            'planned_payment_date'
        )

    if changed_fields:
        update_fields = list(
            changed_fields
        )

        if any(field.name == 'updated_at' for field in invoice._meta.fields):
            update_fields.append(
                'updated_at'
            )

        invoice.save(
            update_fields=update_fields
        )

        if old_status != new_status:
            create_invoice_log(
                invoice,
                request.user,
                (
                    'Статус документа изменён из списка: '
                    f'{status_choices.get(old_status, old_status)} → '
                    f'{status_choices.get(new_status, new_status)}.'
                )
            )

        if old_planned_payment_date != new_planned_payment_date:
            old_date_display = (
                old_planned_payment_date.strftime('%d.%m.%Y')
                if old_planned_payment_date
                else 'не указана'
            )
            new_date_display = new_planned_payment_date.strftime(
                '%d.%m.%Y'
            )

            create_invoice_log(
                invoice,
                request.user,
                (
                    'Плановая дата оплаты изменена из списка: '
                    f'{old_date_display} → {new_date_display}.'
                )
            )

        messages.success(
            request,
            f'Документ #{invoice.id} обновлён.'
        )

    else:
        messages.info(
            request,
            f'По документу #{invoice.id} изменений нет.'
        )

    return _redirect_after_quick_update(
        request
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

            amount_confirmation_requested = (
                request.POST.get(
                    'confirm_amount'
                ) == '1'
            )

            should_sync_amount_verification = (
                amount_changed
                or amount_confirmation_requested
            )

            invoice = form.save()

            verification_message = ""

            if should_sync_amount_verification:
                (
                    _verification_changed,
                    verification_message,
                ) = sync_invoice_amount_verification(
                    invoice,
                    source_label='редактирования документа'
                )

            create_invoice_log(
                invoice,
                request.user,
                'Документ отредактирован'
            )

            if should_sync_amount_verification:
                create_invoice_log(
                    invoice,
                    request.user,
                    verification_message
                )

                if invoice.amount_verified:
                    if invoice.ocr_verified:
                        messages.success(
                            request,
                            (
                                'Сумма подтверждена вручную '
                                'и совпадает с OCR-суммой.'
                            )
                        )

                    elif invoice.ocr_amount is None:
                        messages.success(
                            request,
                            (
                                'Сумма подтверждена вручную. '
                                'OCR-сумма не определена.'
                            )
                        )

                    else:
                        messages.warning(
                            request,
                            (
                                'Сумма подтверждена вручную '
                                'и будет использоваться для оплаты. '
                                'Она отличается от OCR-суммы.'
                            )
                        )

                else:
                    messages.warning(
                        request,
                        (
                            'Сумма не подтверждена. '
                            'Укажите положительную сумму.'
                        )
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
                            "Сумма документа изменена при наличии активного "
                            f"реестра оплаты: {registry_numbers}."
                        )
                    )

                    messages.warning(
                        request,
                        (
                            "Документ уже есть в активном реестре оплаты "
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
