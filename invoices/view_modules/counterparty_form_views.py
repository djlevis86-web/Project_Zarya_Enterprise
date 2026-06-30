from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from ..forms import CounterpartyManualForm
from ..models import Counterparty


@staff_member_required
def counterparty_create(request):

    if request.method == 'POST':

        form = CounterpartyManualForm(
            request.POST
        )

        if form.is_valid():

            counterparty = form.save(
                commit=False
            )

            counterparty.source = Counterparty.SOURCE_MANUAL

            counterparty.sync_comment = (
                'Создан вручную через интерфейс Project Zarya'
            )

            counterparty.save()

            messages.success(
                request,
                'Контрагент успешно создан.'
            )

            return redirect(
                'counterparty_detail',
                counterparty_id=counterparty.id
            )

    else:

        form = CounterpartyManualForm(
            initial={
                'is_active': True,
            }
        )

    return render(
        request,
        'invoices/counterparty_form.html',
        {
            'form': form,
            'page_title': 'Добавить контрагента',
            'submit_label': 'Создать контрагента',
            'counterparty': None,
        }
    )

@staff_member_required
def counterparty_edit(request, counterparty_id):

    counterparty = get_object_or_404(
        Counterparty,
        id=counterparty_id
    )

    if counterparty.source == Counterparty.SOURCE_1C:

        messages.error(
            request,
            (
                'Контрагента из 1С нельзя редактировать вручную. '
                'Измените данные в 1С и выполните импорт справочника.'
            )
        )

        return redirect(
            'counterparty_detail',
            counterparty_id=counterparty.id
        )

    if request.method == 'POST':

        form = CounterpartyManualForm(
            request.POST,
            instance=counterparty
        )

        if form.is_valid():

            counterparty = form.save(
                commit=False
            )

            counterparty.source = Counterparty.SOURCE_MANUAL

            counterparty.sync_comment = (
                'Обновлен вручную через интерфейс Project Zarya'
            )

            counterparty.save()

            messages.success(
                request,
                'Контрагент успешно обновлен.'
            )

            return redirect(
                'counterparty_detail',
                counterparty_id=counterparty.id
            )

    else:

        form = CounterpartyManualForm(
            instance=counterparty
        )

    return render(
        request,
        'invoices/counterparty_form.html',
        {
            'form': form,
            'page_title': 'Редактировать контрагента',
            'submit_label': 'Сохранить изменения',
            'counterparty': counterparty,
        }
    )
