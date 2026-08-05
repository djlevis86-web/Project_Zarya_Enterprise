# Project Zarya Design System V20

## Статус

Этот документ — обязательный визуальный контракт всего Project Zarya.

Новые модули сразу создаются по этому стандарту. Существующие модули
переводятся поэтапно, но не получают собственную параллельную систему
кнопок, иконок, статусов, таблиц или фильтров.

## Источники истины

- Токены: `static/css/base/variables.css`
- Иконки: `templates/components/zds_icon_sprite_v1.html`
- Иконки CSS: `static/css/components/icons.css`
- Кнопки: `static/css/components/buttons.css`
- Статусы: `static/css/components/badges.css`
- Таблицы: `static/css/components/tables.css`
- Фильтры: `static/css/components/filters.css`
- Пагинация: `static/css/components/pagination.css`
- Точка импорта: `static/css/app.css`

Page-level CSS отвечает только за компоновку и уникальное содержимое
страницы. Внешний вид общих компонентов на странице не переопределяется.

## Иконки

Основной стиль — двутонный. Контурный стиль используется для вторичных
действий. Заливка применяется только для статусов, выбранных состояний и
явного семантического акцента.

Иконки загружаются только из локального SVG-спрайта. CDN, icon-font,
эмодзи и внешние SVG в production-интерфейсе не используются.

Стандартный шаблон:

```html
<svg class="zds-icon" viewBox="0 0 24 24" aria-hidden="true">
    <use href="#z-icon-search"></use>
</svg>
```

Интерактивный icon-only control обязан иметь `aria-label` и `title`.

## Кнопки

Иерархия:

1. `zds-button--primary` — главное действие страницы.
2. `zds-button--secondary` — обычное вспомогательное действие.
3. `zds-button--tertiary` — действие с минимальным визуальным весом.
4. `zds-button--danger` — опасная необратимая операция.
5. `zds-button--text` — переход без кнопочного контейнера.

Размеры:

- Large: 42 px — главное действие страницы.
- Medium: 36 px — формы и карточки.
- Compact: 32 px — таблицы и второстепенные действия.
- Icon: 32 × 32 px — только иконка.

Текст кнопки не переносится на desktop. На мобильном кнопка может стать
полноширинной, но её подпись остаётся цельной.

## Статусы

Семантика едина во всём проекте:

- success — утверждён, готов, оплачен, выполнено;
- warning — требует проверки, ожидает, предупреждение;
- danger — ошибка, отклонён, просрочен;
- info — в работе, информационное состояние;
- neutral — новый, архив, недоступно, неактивно.

Цвет не является единственным носителем смысла. Статус содержит текст,
а при необходимости — иконку.

## Таблицы

Используется единый API `zds-table`.

Поддерживаемые состояния строк:

- normal;
- hover;
- selected;
- overdue;
- warning;
- error;
- disabled.

Числовые значения выравниваются вправо и используют tabular numbers.
Состояние строки обозначается спокойным фоном, боковым акцентом, badge и
текстом — без сплошной яркой заливки.

## Фильтры

На desktop фильтры формируют единую горизонтальную систему. На планшете
переносятся по сетке, на мобильном становятся одной колонкой.

Периоды и быстрые условия используют `zds-filter-chip`. Кнопка применения
не должна переносить текст.

## Пагинация

Пагинация использует `zds-pagination`. Параметры активных фильтров
сохраняются при переходе между страницами.

## Доступность

- Все интерактивные элементы доступны с клавиатуры.
- Используется глобальный `:focus-visible`.
- Минимальная touch-цель на coarse pointer — 44 px.
- `prefers-reduced-motion` отключает декоративное движение.
- Иконки, не несущие отдельного смысла, имеют `aria-hidden="true"`.

## Запрещено

- локальные копии глобальных компонентов в page CSS;
- `!important` как средство исправления каскада;
- `:has()` и позиционные селекторы для бизнес-состояний;
- inline styles;
- внешние иконки/CDN;
- новые raw-цвета в page CSS;
- отдельная визуальная семантика статусов для одного модуля;
- кнопки с переносом текста на две строки.

## Порядок внедрения

1. V20.2A — глобальный фундамент и совместимость.
2. V20.2B — График платежей.
3. V20.2C — Реестр оплаты.
4. Документы к оплате и карточка документа.
5. Загрузка и журнал.
6. Справочники и контроль.
7. Система и администрирование.

## V20.2B — График платежей: premium adaptive workspace reference

`templates/invoices/payment_schedule.html` — эталон финансовой рабочей
области Project Zarya. Этап не принимается только по техническим тестам:
после каждого структурного изменения обязательны фактические screenshots
desktop, tablet и mobile.

Обязательная desktop-композиция:

1. компактный command header с периодом и двумя действиями;
2. оперативная KPI-полоса из пяти показателей без обрезки сумм;
3. компактная панель основных фильтров;
4. раскрываемые дополнительные условия;
5. аналитическая зона «график + риски»;
6. платёжная очередь по 12 записей на страницу;
7. не более пяти документов внимания.

Обязательная tablet-композиция:

1. сбалансированная KPI-сетка;
2. компактные фильтры без наложения подписей и controls;
3. график перед рисками периода;
4. платёжная очередь в закрываемой рабочей секции;
5. документы внимания в отдельной закрываемой секции.

Обязательная mobile-композиция:

1. command header;
2. компактные KPI;
3. закрытая по умолчанию панель фильтров;
4. ближайший платёж;
5. график высотой около 190 px;
6. три крупнейших обязательства;
7. закрытая по умолчанию полная очередь;
8. закрытая по умолчанию секция документов внимания.

Правила premium adaptive workspace:

- главный экран сохраняет порядок: состояние → ближайшее действие →
  динамика → приоритетные обязательства → полная очередь;
- суммы KPI не скрываются через ellipsis;
- фильтры не должны визуально конкурировать с аналитикой;
- прямые дочерние блоки canonical filter grid занимают полный ряд;
- дополнительные условия раскрываются только по запросу пользователя;
- график различает будущие, сегодняшние и просроченные даты;
- тренд графика показывает накопительный план тех же данных;
- при разреженных данных ненулевые столбцы получают числовые подписи;
- desktop-очередь ограничена 12 строками на страницу;
- tablet не показывает длинную очередь до раскрытия пользователем;
- mobile показывает три обязательства, а полную очередь скрывает в details;
- page CSS управляет только уникальной композицией и local hooks;
- глобальные `.zds-*` компоненты не переопределяются на уровне страницы;
- запрещено объявлять V20.2B закрытым без визуального сравнения с макетом.

Глобальный API:

- действия — `zds-button`;
- периоды и активные условия — `zds-filter-chip`;
- поля — `zds-filter-field`;
- desktop/tablet очередь — `zds-table`;
- готовность — `zds-badge`;
- навигация страниц — `zds-pagination`;
- графические символы — локальный ZDS SVG-спрайт.

Responsive ownership:

- desktop, tablet и mobile используют отдельные semantic layout hooks;
- responsive-представления могут повторять одни данные в разных
  структурах, но не меняют backend-смысл;
- скрытые по breakpoint представления не должны создавать одинаковые id;
- полная мобильная очередь остаётся доступной через disclosure;
- visual acceptance является отдельным gate после targeted tests.

## V20.2B — visual reconciliation after screenshots 99

The premium adaptive composition is preserved, but the final visual
contract adds three mandatory rules:

- mobile KPI items are compact operational rows, not five tall cards;
- the period separator must never render as a detached line on a phone;
- chart totals must describe only the amount represented by dated points.

The chart header therefore separates:

- `На графике` — amount and document count represented by
  `payment_series`;
- `Вне графика` — selected amount without a point in the current
  31-day chart window, including undated obligations.

The global total remains available in KPI and queue surfaces. A chart
must not display the global total when its bars represent only a small
dated subset.

The right-side analytical panel is named `Крупнейшие обязательства`
unless its data is explicitly restricted to actual risk states.

## V20.2C — premium registry workspace and export confirmation

The payment registry is a financial work centre, not a collection of
legacy cards and GET links.

Required structure:

- compact command header;
- four operational KPI values;
- active-registry workspace plus readiness summary;
- dense document queue with compact filters;
- premium detail and history surfaces;
- global ZDS buttons, badges, tables, filters, pagination and modal;
- page CSS must not own canonical `.zds-*` APIs.

Draft Excel and 1C exports are separate POST-only operations:

- each format has its own form and CSRF token;
- each format opens a financial confirmation modal;
- modal shows registry number, document count, total amount and format;
- financial modal may close through Escape or explicit Cancel, but not
  by clicking the backdrop;
- backend permissions and readiness checks remain authoritative;
- GET export requests redirect without changing the registry;
- successful attachment responses also enqueue a success message;
- the page runtime downloads the attachment, shows immediate feedback
  and reloads the registry state;
- validation failures follow the backend redirect and server message.

The shared interaction layer owns modal behaviour. Registry page CSS
owns only local layout and content density.

## V20.2C — visual reconciliation after screenshots 101

The first premium registry implementation passed its technical gate,
but visual acceptance requires these additional rules:

- every registry KPI card must contain its icon owner; content must
  never be placed into the 36 px icon track;
- registry detail KPI values must remain readable at 393–480 px;
- history desktop and tablet must use a compact seven-column journal,
  not an eleven-column spreadsheet with horizontal scrolling;
- history mobile cards show seven business groups:
  registry, status, documents, amount, creation, latest event and
  actions;
- separate created/exported/paid timestamps are combined into a single
  `Последнее событие` block;
- financial modal close controls use the global `z-icon-close` symbol
  and must never look like an empty square.

The export POST, CSRF, permissions, readiness checks and download
runtime remain unchanged.

### V20.2C page-local action hooks

Page CSS must not select global `.zds-button` classes, including inside
compound selectors. When local layout needs a full-width or positional
hook, the template adds a page-owned class such as
`.registry-history-open` alongside the global ZDS class.

### V20.2C financial modal close icon owner

A sprite `<use href="#z-icon-close">` is not sufficient by itself.
The rendered SVG must also carry the global `.zds-icon` class because
that owner supplies `fill: none`, `stroke: currentColor`, stroke width,
line caps and line joins.

Financial modal close icons therefore use:

`class="zds-icon registry-export-close-icon"`

The page-local class controls only size and placement. It must not
duplicate the global stroke contract.

### V20.2C financial modal spacing

Financial export dialogs use page-local layout hooks for spacing while
global ZDS owners continue to define modal, button and icon appearance.

Desktop contract:
- surface width: up to 600 px;
- header inset: 24 px horizontally;
- form/body inset: 24 px;
- footer remains inside the body inset;
- summary, warning and actions are separated by visible gaps.

Mobile contract:
- surface inset from viewport: 10 px on each side;
- header/body inset: 16 px;
- summary cards keep at least 64 px height;
- warning and actions do not touch the surface border.

Local hooks:
- `.registry-export-modal-header`;
- `.registry-export-modal-heading`;
- `.registry-export-modal-footer`.

Page CSS must not style global `.z-modal-*` or `.zds-*` owners directly.

### V20.2C full-suite compatibility contract

The premium payment registry keeps page-local visual owners and also
carries the global page-header semantic classes:

- `.page-header.page-header-v1`;
- `.page-header-copy-v1`;
- `.page-header-actions-v1`;
- `.page-title`;
- `.page-subtitle`.

These semantic classes are additive and do not replace the local
`.registry-command-*` layout owners.

The payment registry queue does not render disabled selection controls
for blocked documents. It renders a direct `Исправить` action and omits
`invoice_ids` controls until the document becomes ready.

The compact history journal exposes paid time through
`Последнее событие` and the `Оплачен` event rather than restoring the
retired `Факт. оплата` column.

Legacy `.enterprise-registry-*`, `production-panel` and
`.enterprise-table` markers remain retired. Brand regression tests
must validate current ZDS and local page owners instead.

The same additive semantic header contract applies to
`payment_registry_detail.html`. Both registry surfaces retain their
local `.registry-command-*` layout owners while exposing exactly one
global page header, copy, actions, title and subtitle semantic token.

The additive semantic header contract also applies to
`payment_schedule.html`. Its premium `.schedule-command-*` classes
remain the page-layout owners, while global page-header semantic classes
are exposed exactly once for cross-project accessibility and regression
scope.
