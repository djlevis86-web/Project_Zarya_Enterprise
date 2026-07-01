# UI Buttons and Badges Findings

## Главный вывод

Кнопки и бейджи нельзя чинить новым CSS-файлом поверх существующих стилей.

Инвентаризация показала, что правила для кнопок и статусов находятся сразу в нескольких слоях:

- static/css/components/buttons.css;
- static/css/components/badges.css;
- static/css/components/filters.css;
- static/css/components/forms.css;
- static/css/components/tables.css;
- static/css/features/ocr.css;
- static/css/features/table-clean-baseline.css;
- static/css/features/ui-polish-actions.css;
- static/css/features/partial-payments.css.

## Риск

Если добавить новый файл поверх этих правил, получится очередная CSS-заплатка.

## Правильный следующий шаг

Следующий этап должен быть не добавлением нового CSS, а разбором существующих файлов:

1. buttons.css — оставить базовые варианты кнопок.
2. badges.css — оставить базовые варианты статусов.
3. filters.css/forms.css/tables.css — убрать или ограничить переопределения кнопок.
4. features/table-clean-baseline.css и features/ui-polish-actions.css — проверить на дубли.
5. Только после этого менять внешний вид.

## Первый безопасный технический шаг

Создать отдельную ветку:

feature-ui-buttons-badges-cleanup-v1

В ней сначала ничего не красить, а только:

- найти дублирующиеся CSS-правила;
- отметить, какие правила являются базовыми;
- отметить, какие правила являются временными заплатками;
- подготовить точечный план удаления/переноса.

## Что не делать

- не добавлять action-bars.css;
- не добавлять новый buttons-fix.css;
- не менять page-header;
- не править payment_registry.html на глаз;
- не чинить один скриншот отдельной заплаткой.
