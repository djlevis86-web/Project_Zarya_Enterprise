from urllib.parse import parse_qsl, urlencode

from ..payment_registry_services import EDITABLE_REGISTRY_STATUSES, mark_payment_registry_dirty_after_edit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Invoice,
    PaymentRegistry,
    PaymentRegistryItem,
)
from ..payment_registry_permissions import (
    require_payment_registry_permission,
    user_can_cancel_payment_registry,
    user_can_check_payment_registry,
    user_can_manage_payment_registry,
    user_can_mark_payment_registry_paid,
)
from ..payment_registry_services import (
    add_invoice_to_payment_registry,
    cancel_payment_registry,
    check_payment_registry,
    mark_payment_registry_as_paid,
    recalculate_payment_registry,
)



def _format_added_documents_message(registry_id, count):
    count = int(count)
    last_two_digits = count % 100
    last_digit = count % 10

    if 11 <= last_two_digits <= 14:
        noun = 'документов'
    elif last_digit == 1:
        noun = 'документ'
    elif last_digit in (2, 3, 4):
        noun = 'документа'
    else:
        noun = 'документов'

    if noun == 'документ':
        return f'В реестр №{registry_id} добавлен {count} документ.'

    return f'В реестр №{registry_id} добавлено {count} {noun}.'


PAYMENT_REGISTRY_RETURN_QUERY_KEYS = frozenset(
    {
        "q",
        "status",
        "counterparty",
        "payment_status",
        "ocr_status",
        "date_from",
        "date_to",
        "page",
    }
)
PAYMENT_REGISTRY_RETURN_QUERY_MAX_LENGTH = 2048
PAYMENT_REGISTRY_RETURN_VALUE_MAX_LENGTH = 200


def _payment_registry_return_url(request):
    default_url = reverse(
        "payment_registry"
    )
    raw_query = request.POST.get(
        "return_query",
        "",
    ).strip()

    if (
        not raw_query
        or len(raw_query)
        > PAYMENT_REGISTRY_RETURN_QUERY_MAX_LENGTH
    ):
        return default_url

    try:
        query_pairs = parse_qsl(
            raw_query,
            keep_blank_values=True,
            max_num_fields=20,
        )
    except ValueError:
        return default_url

    clean_query = {}

    for key, value in query_pairs:
        if (
            key
            not in PAYMENT_REGISTRY_RETURN_QUERY_KEYS
            or key in clean_query
            or len(value)
            > PAYMENT_REGISTRY_RETURN_VALUE_MAX_LENGTH
        ):
            continue

        clean_query[key] = value

    encoded_query = urlencode(
        clean_query
    )

    if not encoded_query:
        return default_url

    return (
        default_url
        + "?"
        + encoded_query
    )


@login_required
@require_payment_registry_permission(
    user_can_manage_payment_registry,
    'Нет прав на добавление документов в реестр оплаты.',
)
def add_to_payment_registry(request):

    if request.method != 'POST':

        messages.warning(
            request,
            'Добавлять документы в реестр можно только из формы.'
        )

        return redirect(
            'payment_schedule'
        )

    invoice_ids = request.POST.getlist(
        'invoice_ids'
    )

    if not invoice_ids:

        messages.warning(
            request,
            'Выбери хотя бы один документ для добавления в реестр.'
        )

        return redirect(
            _payment_registry_return_url(
                request
            )
        )

    from ..payment_registry_services import (
        add_invoice_to_payment_registry,
        get_or_create_draft_payment_registry,
    )

    registry, created = get_or_create_draft_payment_registry(
        request.user
    )

    invoices = (
        Invoice.objects
        .select_related(
            'counterparty',
            'user'
        )
        .filter(
            id__in=invoice_ids
        )
    )

    added_count = 0
    skipped_messages = []
    warning_messages = []

    for invoice in invoices:

        item, errors, warnings = add_invoice_to_payment_registry(
            invoice,
            registry
        )

        if item:

            added_count += 1

        if errors:

            skipped_messages.append(
                f'Документ №{invoice.id}: ' + '; '.join(errors)
            )

        if warnings:

            warning_messages.append(
                f'Документ №{invoice.id}: ' + '; '.join(warnings)
            )

    if added_count:

        messages.success(
            request,
            _format_added_documents_message(registry.id, added_count)
        )

    if skipped_messages:

        messages.warning(
            request,
            'Не добавлено: ' + ' | '.join(skipped_messages[:5])
        )

    if warning_messages:

        messages.warning(
            request,
            ' | '.join(warning_messages[:5])
        )

    if created and not added_count:

        registry.delete()

    return redirect(
        _payment_registry_return_url(
            request
        )
    )

@login_required
@require_payment_registry_permission(
    user_can_manage_payment_registry,
    'Нет прав на удаление документов из редактируемого реестра.',
)
def remove_from_payment_registry_item(request, item_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Удалять документы из реестра можно только из формы.'
        )

        return redirect(
            'payment_registry'
        )

    from ..models import PaymentRegistry, PaymentRegistryItem
    from ..payment_registry_services import recalculate_payment_registry

    item = (
        PaymentRegistryItem.objects
        .select_related(
            'registry',
            'invoice',
        )
        .filter(
            id=item_id,
            registry__status__in=EDITABLE_REGISTRY_STATUSES,
        )
        .exclude(
            status=PaymentRegistryItem.STATUS_CANCELLED
        )
        .first()
    )

    if not item:

        messages.warning(
            request,
            'Строка реестра не найдена или уже удалена.'
        )

        return redirect(
            'payment_registry'
        )

    registry = item.registry
    invoice_id = item.invoice_id

    item.status = PaymentRegistryItem.STATUS_CANCELLED
    item.save(
        update_fields=(
            'status',
        )
    )

    mark_payment_registry_dirty_after_edit(
        registry
    )

    recalculate_payment_registry(
        registry
    )

    messages.success(
        request,
        f'Документ №{invoice_id} удалён из реестра №{registry.id}. Если реестр уже выгружали, выгрузите его повторно.'
    )

    return redirect(
        'payment_registry_detail',
        registry.id,
    )

@login_required
@require_payment_registry_permission(
    user_can_check_payment_registry,
    'Нет прав на проверку реестра оплаты.',
)
def check_payment_registry_view(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Проверять реестр можно только из формы.'
        )

        return redirect(
            'payment_registry'
        )

    from ..models import PaymentRegistry
    from ..payment_registry_services import check_payment_registry

    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
            status__in=EDITABLE_REGISTRY_STATUSES,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Редактируемый реестр не найден.'
        )

        return redirect(
            'payment_registry'
        )

    result = check_payment_registry(
        registry
    )

    if result['items_count'] == 0:

        messages.warning(
            request,
            f'Реестр №{registry.id} пуст. Сначала добавь документы.'
        )

        return redirect(
            'payment_registry'
        )

    if result['errors_count']:

        messages.warning(
            request,
            f'Реестр №{registry.id} не готов к выгрузке: ошибок {result["errors_count"]}.'
        )

        for error in result['errors'][:5]:

            messages.warning(
                request,
                f'Документ #{error["invoice_id"]}: ' + '; '.join(error['messages'])
            )

    else:

        messages.success(
            request,
            f'Реестр №{registry.id} проверен: к выгрузке готово {result["ready_count"]} документов.'
        )

    if result['warnings_count']:

        messages.info(
            request,
            f'Предупреждений: {result["warnings_count"]}.'
        )

    return redirect(
        'payment_registry'
    )

@login_required
@require_payment_registry_permission(
    user_can_mark_payment_registry_paid,
    'Нет прав на отметку реестра оплаченным.',
)
def mark_payment_registry_paid(request, registry_id):
    registry = get_object_or_404(
        PaymentRegistry,
        id=registry_id
    )

    if (
        not request.user.is_staff
        and not request.user.is_superuser
        and registry.created_by_id != request.user.id
    ):
        raise PermissionDenied

    if request.method != "POST":
        return redirect(
            "payment_registry_detail",
            registry_id=registry.id
        )

    try:
        result = mark_payment_registry_as_paid(
            registry,
            user=request.user
        )
    except ValueError as error:
        messages.error(
            request,
            str(error)
        )

        return redirect(
            "payment_registry_detail",
            registry_id=registry.id
        )

    messages.success(
        request,
        (
            "Реестр отмечен оплаченным. "
            f"Создано оплат: {result.get('paid_count', 0)}. "
            f"Пропущено закрытых документов: {result.get('skipped_count', 0)}."
        )
    )

    return redirect(
        "payment_registry_detail",
        registry_id=registry.id
    )

@login_required
@require_payment_registry_permission(
    user_can_cancel_payment_registry,
    'Нет прав на отмену реестра оплаты.',
)
def cancel_payment_registry_view(request, registry_id):

    if request.method != 'POST':

        messages.warning(
            request,
            'Отменить реестр можно только из формы.'
        )

        return redirect(
            'payment_registry_detail',
            registry_id=registry_id,
        )

    from ..models import PaymentRegistry
    from ..payment_registry_services import cancel_payment_registry

    registry = (
        PaymentRegistry.objects
        .filter(
            id=registry_id,
        )
        .first()
    )

    if not registry:

        messages.warning(
            request,
            'Реестр оплаты не найден.'
        )

        return redirect(
            'payment_registry_history'
        )

    if not request.user.is_staff and registry.created_by_id != request.user.id:

        messages.warning(
            request,
            'Нет доступа к этому реестру.'
        )

        return redirect(
            'payment_registry_history'
        )

    reason = request.POST.get(
        'reason',
        ''
    ).strip()

    cancelled = cancel_payment_registry(
        registry,
        user=request.user,
        reason=reason,
    )

    if not cancelled:

        messages.warning(
            request,
            'Можно отменить только черновик или проверенный реестр.'
        )

        return redirect(
            'payment_registry_detail',
            registry_id=registry.id,
        )

    messages.success(
        request,
        f'Реестр оплаты №{registry.id} отменён.'
    )

    return redirect(
        'payment_registry_detail',
        registry_id=registry.id,
    )
