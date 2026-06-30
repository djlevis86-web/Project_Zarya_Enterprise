# UI Audit Findings — Project Zarya Enterprise

## Общий вывод

UI проекта находится в рабочем состоянии.

Проверено:
- страница входа открывается;
- внутренние страницы открываются;
- app.css подключается;
- критических 500-ошибок в smoke-аудите нет;
- разграничение ролей работает корректно;
- production-проверка и passenger_wsgi.py работают.

Smoke-аудит:
- Total checks: 37
- Failed checks: 0

## Структура UI

Найдено:
- HTML templates: 36
- CSS files: 38
- JS files: 3

Почти все страницы наследуются от base.html.

## Крупные шаблоны

Главные кандидаты на UI-рефакторинг:
- templates/invoices/detail.html — 925 строк
- templates/invoices/payment_registry.html — 891 строк
- templates/invoices/counterparty_detail.html — 542 строки
- templates/invoices/invoice_list.html — 516 строк
- templates/dashboard.html — 450 строк
- templates/invoices/payment_registry_detail.html — 442 строки
- templates/invoices/payment_schedule.html — 390 строк

## Основные UI-проблемы

1. Нет единой системы page header.
2. Нужно оформить empty states.
3. Нужно унифицировать таблицы.
4. Нужно унифицировать карточки.
5. Нужно унифицировать кнопки и бейджи.
6. Крупные шаблоны нужно постепенно разбивать на partials.
7. Inline JavaScript позже лучше вынести в static/js.

## Приоритет UI-работ

UI-1. Page headers + empty states.
UI-2. Buttons + badges.
UI-3. Tables.
UI-4. Dashboard.
UI-5. Invoice list + upload pages.
UI-6. Invoice detail.
UI-7. Payment registry.

## Правила UI-правок

1. Не менять бизнес-логику вместе с UI.
2. Не менять права доступа вместе с UI.
3. Не делать большие переписывания одним коммитом.
4. Не добавлять inline CSS.
5. Новые стили добавлять в существующую CSS-структуру.
6. Сначала компоненты, потом страницы.
7. После каждого этапа запускать smoke-проверку.
8. После каждого этапа проверять production settings и collectstatic.

## Первый рекомендуемый этап

Начать с ветки:
feature-ui-page-headers-empty-states-v1

Состав этапа:
1. Создать единый CSS для page headers.
2. Создать единый CSS для empty states.
3. Добавить empty-state на список счетов.
4. Добавить empty-state на загрузки.
5. Добавить empty-state на OCR-очередь.
6. Добавить empty-state на платежный реестр.
7. Добавить empty-state на аудит.
8. Проверить роли.
9. Проверить production collectstatic.
