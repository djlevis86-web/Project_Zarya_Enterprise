from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from ..forms import InvoiceCounterpartyAssignForm
from ..log_service import create_invoice_log
from ..models import Invoice


@staff_member_required
def invoice_assign_counterparty(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if request.method == 'POST':

        form = InvoiceCounterpartyAssignForm(
            request.POST
        )

        if form.is_valid():

            counterparty = form.cleaned_data[
                'counterparty'
            ]

            invoice.counterparty = counterparty

            invoice.counterparty_match_status = (
                Invoice.COUNTERPARTY_MATCH_FOUND
            )

            invoice.counterparty_match_comment = (
                f'Контрагент привязан вручную: {counterparty.name}'
            )

            invoice.save(
                update_fields=[
                    'counterparty',
                    'counterparty_match_status',
                    'counterparty_match_comment',
                ]
            )

            create_invoice_log(
                invoice,
                request.user,
                f'Контрагент привязан вручную: {counterparty.name}'
            )

            messages.success(
                request,
                'Контрагент успешно привязан к счету.'
            )

            next_url = request.POST.get(
                'next'
            )

            if next_url:

                return redirect(
                    next_url
                )

            return redirect(
                'invoice_detail',
                invoice_id=invoice.id
            )

    else:

        form = InvoiceCounterpartyAssignForm()

    return render(
        request,
        'invoices/invoice_assign_counterparty.html',
        {
            'invoice': invoice,
            'form': form,
        }
    )
