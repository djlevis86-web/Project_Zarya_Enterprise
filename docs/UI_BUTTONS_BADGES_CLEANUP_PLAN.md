# UI Buttons and Badges Cleanup Plan

## 1. Цель

Цель этапа — подготовить безопасный план чистки CSS для кнопок и бейджей без визуальных правок.

На этом этапе запрещено менять:

- static/css/*.css;
- templates/*.html;
- JavaScript;
- бизнес-логику;
- права доступа.

Разрешено только:

- собрать карту CSS-правил;
- определить базовые и временные слои;
- описать порядок будущей чистки.

---

## 2. Файлы, которые участвуют в кнопках и бейджах

### Базовые файлы

- static/css/components/buttons.css;
- static/css/components/badges.css.

Именно здесь должны жить основные правила для:

- .btn;
- .btn-primary;
- .btn-secondary;
- .btn-danger;
- .btn-sm;
- .btn-xs;
- .btn-lg;
- .status-badge;
- .ocr-badge.

### Контекстные файлы

- static/css/components/forms.css;
- static/css/components/filters.css;
- static/css/components/tables.css.

Эти файлы могут управлять расположением кнопок, но не должны полностью переопределять их внешний вид.

### Рискованные feature-файлы

- static/css/features/ocr.css;
- static/css/features/table-clean-baseline.css;
- static/css/features/ui-polish-actions.css;
- static/css/features/partial-payments.css.

Эти файлы нужно проверять особенно внимательно, потому что они могут содержать поздние заплатки.

---

## 3. Главная проблема

Сейчас кнопки и бейджи описаны не в одном месте.

Из-за этого одна и та же кнопка может получать стиль из нескольких CSS-слоёв:

1. базовый стиль из components/buttons.css;
2. контекстный стиль из forms.css или filters.css;
3. табличный стиль из tables.css;
4. feature-переопределение из table-clean-baseline.css или ui-polish-actions.css.

Такой подход делает UI нестабильным.

---

## 4. Правило будущей чистки

Нельзя добавлять новый CSS-файл для исправления кнопок.

Правильный подход:

1. buttons.css — базовый внешний вид кнопок;
2. badges.css — базовый внешний вид статусов;
3. forms.css / filters.css — только layout кнопок в формах и фильтрах;
4. tables.css — только layout кнопок внутри таблиц;
5. feature-файлы — только специфичные исключения, если их нельзя удалить.

---

## 5. Что считать базовым

### Кнопки

Базовые классы:

- .btn;
- .btn-primary;
- .btn-secondary;
- .btn-danger;
- .btn-sm;
- .btn-xs;
- .btn-lg;
- .btn-block;
- .btn:disabled;
- .btn.is-loading.

### Бейджи

Базовые классы:

- .status-badge;
- .status-draft;
- .status-checked;
- .status-exported;
- .status-partially_paid;
- .status-paid;
- .status-cancelled;
- .ocr-badge;
- .ocr-badge-ok;
- .ocr-badge-warning;
- .ocr-badge-error.

---

## 6. Что считать подозрительным

Подозрительные признаки:

- .btn переопределяется внутри feature-файла;
- .status-badge получает разные размеры на разных страницах;
- disabled-кнопки выглядят как активные;
- статус Черновик выглядит как кнопка;
- кнопки в таблице имеют разную ширину;
- длинная подпись кнопки вылезает из ячейки;
- OCR-статус и финансовый статус выглядят одинаково.

---

## 7. Предлагаемый порядок будущей чистки

### Этап 1. buttons.css

Проверить и зафиксировать базовые стили кнопок.

Не менять HTML.

### Этап 2. badges.css

Проверить и зафиксировать базовые стили статусов.

Не менять HTML.

### Этап 3. tables.css

Ограничить правила таблиц так, чтобы они отвечали только за расположение кнопок внутри ячеек.

### Этап 4. filters.css и forms.css

Оставить только layout-правила для кнопок в формах и фильтрах.

### Этап 5. feature-файлы

Проверить:

- table-clean-baseline.css;
- ui-polish-actions.css;
- ocr.css;
- partial-payments.css.

Удалять или переносить только после проверки страниц.

---

## 8. Страницы для проверки после будущих CSS-правок

Минимальный список:

- dashboard;
- invoice_list;
- invoice_detail;
- ocr_queue;
- payment_schedule;
- payment_registry;
- payment_registry_history;
- payment_registry_detail;
- counterparty_directory;
- counterparty_detail.

---

## 9. Команда следующего реального этапа

Следующий этап после этого документа:

feature-ui-buttons-badges-cleanup-v1

Там можно будет начать править CSS, но только с одного файла:

static/css/components/buttons.css

После этого:

- python manage.py check;
- git diff --check;
- UI smoke;
- визуальная проверка страниц.
