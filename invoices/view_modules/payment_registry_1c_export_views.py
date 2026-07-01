from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from ..models import (
    CompanyRequisites,
    Counterparty,
    Invoice,
    InvoicePayment,
    PaymentRegistry,
    PaymentRegistryItem,
)
from ..payment_registry_permissions import (
    require_payment_registry_permission,
    user_can_export_payment_registry,
)
from ..payment_registry_services import (
    EDITABLE_REGISTRY_STATUSES,
    check_payment_registry,
    recalculate_payment_registry,
)
from .payment_registry_helpers import (
    apply_payment_status_filter,
    apply_positive_payment_balance_filter,
)


@login_required
@require_payment_registry_permission(
    user_can_export_payment_registry,
    'Нет прав на выгрузку реестра оплаты.',
)
def export_payment_registry_draft_1c(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Выгрузка реестра выполняется только из формы.'
        )

        return redirect(
            'payment_registry'
        )





    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
            created_by=request.user,
            status__in=EDITABLE_REGISTRY_STATUSES,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Редактируемый реестр не найден или уже закрыт.'
        )

        return redirect(
            'payment_registry'
        )

    check_result = check_payment_registry(
        registry
    )

    if check_result['items_count'] == 0:

        messages.warning(
            request,
            f'Реестр №{registry.id} пуст. Сначала добавь счета.'
        )

        return redirect(
            'payment_registry'
        )

    if check_result['errors_count']:

        messages.warning(
            request,
            f'Реестр №{registry.id} нельзя выгрузить: ошибок {check_result["errors_count"]}.'
        )

        return redirect(
            'payment_registry'
        )

    items = (
        registry.items
        .select_related(
            'invoice',
            'invoice__counterparty',
            'invoice__user',
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .order_by(
            'planned_payment_date',
            'invoice_id',
        )
    )

    buffer = StringIO()
    writer = csv.writer(
        buffer,
        delimiter=';',
        lineterminator='\n',
    )

    writer.writerow(
        [
            'RegistryID',
            'InvoiceID',
            'InvoiceNumber',
            'Counterparty',
            'INN',
            'KPP',
            'Bank',
            'BankAccount',
            'BIK',
            'CorrAccount',
            'Amount',
            'PaymentDate',
            'Purpose',
        ]
    )

    for item in items:

        invoice = item.invoice
        counterparty = invoice.counterparty
        payment_date = item.planned_payment_date or invoice.planned_payment_date

        purpose = (
            getattr(invoice, 'payment_purpose', '')
            or getattr(invoice, 'purpose', '')
            or getattr(invoice, 'description', '')
            or ''
        )

        writer.writerow(
            [
                registry.id,
                invoice.id,
                invoice.invoice_number or '',
                counterparty.name if counterparty else '',
                getattr(counterparty, 'inn', '') if counterparty else '',
                getattr(counterparty, 'kpp', '') if counterparty else '',
                getattr(counterparty, 'bank_name', '') if counterparty else '',
                getattr(counterparty, 'account_number', '') if counterparty else '',
                getattr(counterparty, 'bik', '') if counterparty else '',
                getattr(counterparty, 'correspondent_account', '') if counterparty else '',
                str(item.amount).replace('.', ','),
                payment_date.strftime('%d.%m.%Y') if payment_date else '',
                purpose,
            ]
        )

    now = timezone.now()

    registry.status = PaymentRegistry.STATUS_EXPORTED
    registry.exported_by = request.user
    registry.exported_at = now
    registry.save(
        update_fields=(
            'status',
            'exported_by',
            'exported_at',
        )
    )

    items.update(
        status=PaymentRegistryItem.STATUS_EXPORTED,
        exported_at=now,
    )

    recalculate_payment_registry(
        registry
    )

    content = '\ufeff' + buffer.getvalue()

    response = HttpResponse(
        content,
        content_type='text/plain; charset=utf-8',
    )

    response['Content-Disposition'] = (
        f'attachment; filename="payment_registry_{registry.id}_1c.txt"'
    )

    return response

@login_required
@require_payment_registry_permission(
    user_can_export_payment_registry,
    'Нет прав на выгрузку реестра оплаты.',
)
def export_payment_registry_1c(request):

    company = CompanyRequisites.objects.first()

    if not company:

        messages.error(
            request,
            'Сначала заполните реквизиты организации в админке.'
        )

        return redirect(
            'payment_registry'
        )

    selected_status = request.GET.get(
        'status',
        Invoice.STATUS_APPROVED
    )

    selected_counterparty = request.GET.get(
        'counterparty',
        ''
    )

    search_query = request.GET.get(
        'q',
        ''
    ).strip()

    date_from = request.GET.get(
        'date_from',
        ''
    ).strip()

    date_to = request.GET.get(
        'date_to',
        ''
    ).strip()

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .exclude(
            status=Invoice.STATUS_PAID
        )
    )

    if selected_status and selected_status != 'all':

        invoices = invoices.filter(
            status=selected_status
        )

    if selected_counterparty:

        invoices = invoices.filter(
            counterparty_id=selected_counterparty
        )

    if search_query:

        invoices = invoices.filter(
            Q(title__icontains=search_query)
            |
            Q(original_filename__icontains=search_query)
            |
            Q(invoice_number__icontains=search_query)
            |
            Q(vendor__icontains=search_query)
            |
            Q(counterparty__name__icontains=search_query)
        )

    if date_from:

        invoices = invoices.filter(
            planned_payment_date__gte=date_from
        )

    if date_to:

        invoices = invoices.filter(
            planned_payment_date__lte=date_to
        )

    invoices = invoices.order_by(
        'planned_payment_date',
        '-payment_priority',
        'counterparty__name',
        'id'
    )

    missing_requisites = []

    for invoice in invoices:

        counterparty = invoice.counterparty

        if not counterparty:

            missing_requisites.append(
                f'Счет #{invoice.id}: контрагент не найден'
            )

            continue

        required_values = [
            counterparty.inn,
            counterparty.bank_name,
            counterparty.bik,
            counterparty.account_number,
        ]

        if any(
            not value
            for value in required_values
        ):

            missing_requisites.append(
                f'Счет #{invoice.id}: {counterparty.name}'
            )

    if missing_requisites:

        messages.error(
            request,
            (
                'Выгрузка 1С TXT остановлена. '
                'Есть контрагенты без обязательных платежных реквизитов.'
            )
        )

        return redirect(
            'counterparties_missing_requisites'
        )

    def clean_value(value):

        if value is None:

            return ''

        value = str(value)

        value = value.replace(
            '\r',
            ' '
        )

        value = value.replace(
            '\n',
            ' '
        )

        value = value.strip()

        return value

    def format_date(value):

        if value:

            return value.strftime(
                '%d.%m.%Y'
            )

        return date.today().strftime(
            '%d.%m.%Y'
        )

    def format_amount(value):

        if not value:

            return '0.00'

        return f'{value:.2f}'

    created_at = datetime.now()

    lines = []

    lines.append(
        '1CClientBankExchange'
    )

    lines.append(
        'ВерсияФормата=1.03'
    )

    lines.append(
        'Кодировка=Windows'
    )

    lines.append(
        'Отправитель=Project Zarya'
    )

    lines.append(
        'Получатель=1С'
    )

    lines.append(
        f'ДатаСоздания={created_at.strftime("%d.%m.%Y")}'
    )

    lines.append(
        f'ВремяСоздания={created_at.strftime("%H:%M:%S")}'
    )

    lines.append(
        f'РасчСчет={clean_value(company.account_number)}'
    )

    for invoice in invoices:

        if not invoice.counterparty:

            continue

        counterparty = invoice.counterparty

        amount = invoice.amount or 0

        payment_date = invoice.planned_payment_date or date.today()

        if invoice.invoice_number:

            payment_purpose = (
                f'Оплата по счету №{invoice.invoice_number}'
            )

            if invoice.invoice_date:

                payment_purpose += (
                    f' от {invoice.invoice_date}'
                )

        else:

            payment_purpose = (
                f'Оплата по счету ID {invoice.id}'
            )

        lines.append(
            'СекцияДокумент=Платежное поручение'
        )

        lines.append(
            f'Номер={invoice.id}'
        )

        lines.append(
            f'Дата={format_date(payment_date)}'
        )

        lines.append(
            f'Сумма={format_amount(amount)}'
        )

        lines.append(
            f'Плательщик={clean_value(company.name)}'
        )

        lines.append(
            f'ПлательщикИНН={clean_value(company.inn)}'
        )

        lines.append(
            f'ПлательщикКПП={clean_value(company.kpp)}'
        )

        lines.append(
            f'ПлательщикСчет={clean_value(company.account_number)}'
        )

        lines.append(
            f'ПлательщикБанк1={clean_value(company.bank_name)}'
        )

        lines.append(
            f'ПлательщикБИК={clean_value(company.bik)}'
        )

        lines.append(
            f'ПлательщикКорсчет={clean_value(company.correspondent_account)}'
        )

        lines.append(
            f'Получатель={clean_value(counterparty.name)}'
        )

        lines.append(
            f'ПолучательИНН={clean_value(counterparty.inn)}'
        )

        lines.append(
            f'ПолучательКПП={clean_value(counterparty.kpp)}'
        )

        lines.append(
            f'ПолучательСчет={clean_value(counterparty.account_number)}'
        )

        lines.append(
            f'ПолучательБанк1={clean_value(counterparty.bank_name)}'
        )

        lines.append(
            f'ПолучательБИК={clean_value(counterparty.bik)}'
        )

        lines.append(
            f'ПолучательКорсчет={clean_value(counterparty.correspondent_account)}'
        )

        lines.append(
            'ВидПлатежа=Электронно'
        )

        lines.append(
            'ВидОплаты=01'
        )

        lines.append(
            'Очередность=5'
        )

        lines.append(
            f'НазначениеПлатежа={clean_value(payment_purpose)}'
        )

        lines.append(
            'КонецДокумента'
        )

    lines.append(
        'КонецФайла'
    )

    content = '\r\n'.join(
        lines
    )

    response = HttpResponse(
        content.encode(
            'cp1251',
            errors='replace'
        ),
        content_type='text/plain; charset=windows-1251'
    )

    response[
        'Content-Disposition'
    ] = (
        'attachment; filename="payment_registry_1c.txt"'
    )

    return response
