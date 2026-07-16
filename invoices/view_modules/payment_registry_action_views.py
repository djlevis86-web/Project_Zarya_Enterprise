from ..payment_registry_services import EDITABLE_REGISTRY_STATUSES, mark_payment_registry_dirty_after_edit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
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
            'payment_schedule'
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
                f'#{invoice.id}: ' + '; '.join(errors)
            )

        if warnings:

            warning_messages.append(
                f'#{invoice.id}: ' + '; '.join(warnings)
            )

    if added_count:

        messages.success(
            request,
            f'Добавлено документов в реестр №{registry.id}: {added_count}.'
        )

    if skipped_messages:

        messages.warning(
            request,
            'Не добавлено: ' + ' | '.join(skipped_messages[:5])
        )

    if warning_messages:

        messages.info(
            request,
            'Предупреждения: ' + ' | '.join(warning_messages[:5])
        )

    if created and not added_count:

        registry.delete()

    return redirect(
        'payment_registry'
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
        f'Документ #{invoice_id} удалён из реестра №{registry.id}. Если реестр уже выгружался, выгрузи его заново.'
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

