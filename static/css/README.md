# CSS structure rules

## Главный файл

Подключается только:

static/css/app.css

## Правило разработки

Новые стили больше не добавляем в:

static/css/style.css

`style.css` временно считается legacy-файлом.

## Куда писать новые стили

base/
- variables.css — CSS-переменные: цвета, радиусы, тени, размеры
- reset.css — базовый сброс
- typography.css — заголовки, текст, ссылки

layout/
- shell.css — общий каркас приложения
- sidebar.css — боковое меню
- topbar.css — верхняя панель

components/
- buttons.css — кнопки
- forms.css — поля, textarea, select, form-group
- tables.css — таблицы
- cards.css — карточки
- badges.css — статусы, бейджи
- filters.css — фильтры
- pagination.css — пагинация

pages/
- dashboard.css
- invoice-list.css
- invoice-detail.css
- payment-schedule.css
- payment-registry.css
- counterparties.css
- profile.css

features/
- partial-payments.css
- ocr.css
- users-roles.css

## Как переносить старый CSS

1. Сначала копируем блок из style.css в нужный модуль.
2. Проверяем страницы.
3. Только после проверки удаляем этот блок из style.css.
4. Делаем отдельный commit.
