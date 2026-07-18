# Project Zarya — сводный backlog расширенных аудитов

**Дата аудитов:** 17 июля 2026 года
**Дата добавления в backlog:** 18 июля 2026 года
**Текущий baseline проекта:** `c36d245`
**Проверенная аудитами версия:** `dfdaf8e`

## Источники

1. `Project_Zarya_Business_Logic_Audit(1).md`
2. `Project_Zarya_Payment_Schedule_Registry_Audit(1).md`
3. `Project_Zarya_Remaining_Subsystems_Deep_Audit(1).md`
4. `Project_Zarya_Design_UI_2026_Audit(1).md`
5. `Project_Zarya_UI_Trends_2026_Implementation_Plan(1).docx`
6. Соответствующие evidence-архивы.

## Правила обработки

- Аудиты выполнены не на текущем `main`.
- Каждая новая находка изначально имеет статус `RECHECK REQUIRED`.
- Находка не считается подтверждённой только по тексту отчёта.
- Перед исправлением требуется reproduction на актуальном коде.
- Независимые риски не объединяются в один большой commit.
- Для каждого изменения обязателен regression-тест.
- Полный suite запускается один раз в рабочей feature-ветке.
- Release выполняется только через `feature → develop → main → production`.
- Evidence-архив используется как диагностический материал, а не как
  доказательство текущего production-состояния.

## Статусы

| Статус | Значение |
|---|---|
| `RECHECK REQUIRED` | Находка получена из старого аудита |
| `CONFIRMED` | Воспроизведена на текущем main |
| `IN PROGRESS` | Выполняется исправление |
| `LOCAL DONE` | Код и тесты прошли в feature-ветке |
| `RELEASED` | Изменение находится в main |
| `DONE` | Выполнена production-проверка |
| `PARTIAL` | Исправлена только часть инварианта |
| `NOT REPRODUCED` | На текущем коде дефект не воспроизводится |
| `ACCEPTED RISK` | Риск принят с письменным обоснованием |

# 1. Уже устранённые или частично устранённые находки

## DONE — security stability baseline

Исправлены и проверены на production:

- H-01 — защита комментариев от IDOR;
- H-02 — permission gate загрузки;
- H-03 — изменение статуса только через POST;
- M-02 — корректный `PermissionDenied`;
- M-03 — защита от open redirect.

**Production release:** `50fd58e`

## DONE — H-04 backup HTTP safety

- создание backup только через POST;
- удаление backup только через POST;
- CSRF-защита;
- GET возвращает `405`;
- GET не вызывает backup service;
- GET не удаляет файл;
- формы интерфейса используют POST;
- полный suite: `214/214 OK`.

**Feature:** `3919891`
**Develop:** `e1a5b27`
**Production release:** `c36d245`

## PARTIAL — BL-01 / BL-04, подтверждение суммы

Исправлено:

- ручная положительная сумма имеет приоритет над OCR;
- несовпадение с OCR не блокирует реестр;
- несвязанное редактирование не меняет verification state;
- повторный OCR сохраняет ручное подтверждение;
- production-сценарий проверен.

Остаётся:

- структурированные `verified_by`;
- `verified_at`;
- подтверждённое значение;
- метод и причина подтверждения;
- версия документа при подтверждении.

**Production release:** `ce03523`

## PARTIAL — BL-15, ответственный

Исправлено:

- справочник ответственных;
- ответственный обязателен при загрузке и редактировании;
- readiness gate проверяет назначение;
- старое неактивное значение сохраняется для существующего документа.

Остаётся перепроверить:

- правила активности ответственного;
- изменение ответственного после проверки/утверждения;
- snapshot ответственного в исторической выгрузке.

## DONE — согласованность отчёта бота

- dashboard и detail используют согласованную live-логику;
- устранено расхождение summary/detail;
- добавлена защита от N+1.

# 2. P0 — финансовая целостность

## FIN-01 — единая формула остатка и canonical readiness

**Источники:** BL-06, BL-07, payment audit 3–6, 12–15
**Статус:** `RECHECK REQUIRED`

Задачи:

- определить `payable_remaining` как единый источник остатка;
- использовать одинаковый annotated queryset в карточках и таблицах;
- создать структурированный `PaymentReadinessResult`;
- использовать его при отображении, добавлении, проверке, экспорте и оплате;
- блокировать deleted, rejected, inactive и документы без ответственного;
- исключить ложное сообщение «Готово к оплате»;
- добавить query-budget и end-to-end regression-тесты.

## FIN-02 — строгая state machine реестра

**Источники:** BL-08, BL-09, payment audit 16–18
**Статус:** `RECHECK REQUIRED`

Целевая цепочка:

`draft → checked → exported → partially_paid / paid`

Задачи:

- запретить `draft → paid`;
- успешная проверка фиксирует пользователя, время и версию;
- изменение строки инвалидирует проверку;
- все переходы выполняются одним transition service;
- недопустимые переходы проверяются независимо от view.

## FIN-03 — атомарный payment ledger

**Источники:** BL-10, BL-11, BL-19
**Статус:** `RECHECK REQUIRED`

Задачи:

- `InvoicePayment` становится источником фактической оплаты;
- убрать ручное управление `paid_at` из общей формы;
- использовать `transaction.atomic()` и `select_for_update()`;
- исключить конкурентную переплату;
- синхронизировать Invoice, RegistryItem и Registry;
- отмена оплаты должна атомарно восстановить остаток и состояния;
- добавить idempotency key для финансовых операций.

## FIN-04 — immutable registry snapshot

**Источники:** BL-12, BL-13, payment audit 27–32
**Статус:** `RECHECK REQUIRED`

Задачи:

- сохранить snapshot документа и реквизитов при check/export;
- сохранять export-файл и SHA-256;
- повторная выгрузка исторического реестра идентична;
- изменение справочника не меняет старую выгрузку;
- закрыть legacy Excel/1С endpoints, обходящие реестр;
- использовать `Invoice.responsible`, а не случайного пользователя.

## DOC-01 — версия документа и утверждения

**Источники:** BL-05
**Статус:** `RECHECK REQUIRED`

Задачи:

- добавить document version;
- добавить `approved_by`, `approved_at`, `approved_version`;
- вынести статусы из общей ModelForm;
- платёжно-значимое изменение инвалидирует approval;
- добавить transition matrix и аудит причин изменения.

# 3. P0 — OCR и происхождение данных

## OCR-01 — единая политика inline/queued/reprocess OCR

**Источники:** BL-02, BL-03
**Статус:** `RECHECK REQUIRED`

Задачи:

- inline и queued OCR используют один service;
- технический размер файла не влияет на бизнес-результат;
- повторный OCR не стирает ручную сумму;
- повторный OCR не стирает номер, дату, тип и контрагента;
- management-команды используют тот же доменный service;
- OCR хранит кандидаты, а не перезаписывает подтверждённые значения.

## OCR-02 — надёжный worker protocol

**Источники:** remaining subsystems 7–8
**Статус:** `RECHECK REQUIRED`

Задачи:

- удалить или переписать legacy `ocr/tasks.py`;
- оставить один worker protocol;
- атомарный claim задачи;
- одна активная job на документ;
- lease и reclaim зависших jobs;
- retry/backoff и terminal error;
- inline OCR failure создаёт retry job;
- массовый повтор OCR не выполняется внутри HTTP request.

# 4. P0 — пользователи, доступ и сохранность файлов

## USER-01 — защита последнего администратора

**Статус:** `RECHECK REQUIRED`

Задачи:

- запретить самопонижение последнего активного администратора;
- запретить его деактивацию и удаление;
- применять проверку транзакционно;
- вызвать Django password validators;
- разделить бизнес-роль ADMIN и Django superuser;
- фиксировать изменения ролей в AuditLog.

## USER-02 — запрет каскадной потери документов

**Статус:** `RECHECK REQUIRED`

Задачи:

- пересмотреть `Invoice.user on_delete=CASCADE`;
- запретить физическое удаление финансовых пользователей;
- использовать deactivate/retention policy;
- выполнить data audit до изменения constraint;
- добавить regression-тест сохранности счетов.

## FILE-01 — защищённое скачивание документов

**Статус:** `RECHECK REQUIRED`

Задачи:

- закрыть прямую публичную выдачу `/media/invoices/`;
- добавить authenticated download endpoint;
- проверять object visibility;
- не выдавать soft-deleted документы;
- журналировать скачивание;
- проверить конфигурацию Nginx.

## FILE-02 — единая политика soft delete

**Статус:** `RECHECK REQUIRED`

Задачи:

- soft-deleted документ нельзя редактировать по прямому URL;
- удалить его из dashboard, reports, OCR и payment querysets;
- определить восстановление как отдельную операцию;
- определить правила повторной загрузки удалённого документа.

# 5. P0 — загрузка и 1С

## UPLOAD-01 — безопасность и согласованность загрузки

**Источники:** H-06, remaining subsystems 7
**Статус:** `RECHECK REQUIRED`

Задачи:

- лимиты файлов и batch;
- проверка сигнатур PDF/JPEG/PNG;
- ограничения страниц и image pixels;
- cleanup orphan-файлов;
- защита от duplicate race;
- дубликат чужого файла не раскрывает ID/title;
- inline OCR error переводит batch в partial/error;
- исправить отображение `skipped_files`.

## ONEC-01 — атомарный импорт и корректная идентичность

**Источники:** BL-14, remaining subsystems 9
**Статус:** `RECHECK REQUIRED`

Задачи:

- сначала validate/preview, затем commit;
- `clear_ocr=True` не меняет данные до успешной проверки;
- общая транзакция импорта;
- разделить incremental и full snapshot;
- identity key учитывает ИНН + КПП;
- определить политику пустых значений;
- constraints и merge flow для дублей;
- rematch не меняет manual/approved/exported документы;
- background job с progress и отчётом.

# 6. P0 — security, audit и operations

## SEC-01 — production settings fail-closed

**Источники:** H-05
**Статус:** `RECHECK REQUIRED`

Задачи:

- обязательный production `SECRET_KEY`;
- отсутствие insecure fallback;
- secure cookies, HTTPS redirect и HSTS;
- production password validators;
- `manage.py check --deploy`;
- regression-тесты обязательных environment variables.

## EXPORT-01 — защита от spreadsheet formula injection

**Статус:** `RECHECK REQUIRED`

Задачи:

- neutralize значения, начинающиеся с `=`, `+`, `-`, `@`;
- применить к XLSX и CSV;
- добавить regression-тесты;
- проверить все пользовательские и импортированные текстовые поля.

## AUDIT-01 — доказуемый неизменяемый аудит

**Статус:** `RECHECK REQUIRED`

Задачи:

- audit событий пользователей и финансовых операций;
- запретить удаление AuditLog через admin;
- structured actor/time/reason/before/after;
- корректно обрабатывать trusted proxy IP;
- экспорт не должен молча обрезаться на 5000 строк;
- определить retention и внешний sink.

## OPS-01 — health checks и надёжный backup

**Источники:** H-09, remaining subsystems 13
**Статус:** `RECHECK REQUIRED`

Задачи:

- health metric содержит status/error/checked_at;
- DB, storage, Redis, worker, queue, disk и 1С checks;
- SQLite backup через согласованный snapshot;
- PostgreSQL через `pg_dump`/`pg_restore`;
- backup media;
- checksum, encryption, retention и offsite copy;
- автоматический restore drill.

# 7. P1 — отчёты, производительность и UI

## REPORT-01 — единые scopes и финансовые метрики

**Статус:** `RECHECK REQUIRED`

Задачи:

- dashboard исключает soft-deleted;
- использовать актуальный статус `in_work`;
- reports используют ту же visibility policy;
- «Готово к оплате» использует canonical readiness;
- разделить created, planned, approved и paid analytics;
- snapshot/live режимы отчёта имеют явную семантику.

## PERF-01 — пагинация и query budgets

**Статус:** `RECHECK REQUIRED`

Задачи:

- schedule и registry pagination;
- bot report не валидирует всю БД до пагинации;
- directory и audit pagination;
- query-budget tests на 50/1000 строк;
- устранить N+1.

## UI-2026-01 — P0 accessibility и CSS stability

**Статус:** `RECHECK REQUIRED`

Задачи:

- Playwright baseline на 8 viewport;
- mobile navigation;
- исправить contrast primary button;
- `focus-visible`;
- labels/ids и accessible errors;
- skip-link и `aria-current`;
- исправить malformed select CSS;
- убрать duplicate stylesheet import;
- один page heading;
- отделить destructive actions.

## UI-2026-02 — таблицы, формы и финансовые workflows

**Статус:** `RECHECK REQUIRED`

Задачи:

- compact/comfortable density;
- toolbar, sorting, pagination и saved views;
- overflow row actions;
- responsive row expansion;
- sectioned document form;
- sticky save bar и dirty state;
- OCR/user/1C source badges;
- registry process stepper;
- checklist блокирующих причин;
- role-aware actions.

## UI-2026-03 — практический план реализации UI/UX 2026

**Источник:** `Project_Zarya_UI_Trends_2026_Implementation_Plan(1).docx`
**Статус:** `RECHECK REQUIRED`

### P0 — объяснимость и базовая доступность

- для критических полей показывать текущее значение, OCR-кандидат и данные 1С;
- показывать источник, confidence, автора и время подтверждения;
- отдельное действие подтверждения итогового значения;
- повторный OCR не заменяет подтверждённые пользовательские данные;
- глобальный `focus-visible`;
- корректные `label`, `for`, `id` и `aria-describedby`;
- error summary и переход к первому ошибочному полю;
- `aria-live` для OCR, импорта, экспорта и сохранения;
- `aria-sort` для таблиц;
- `prefers-reduced-motion`;
- touch targets основных действий не меньше 44×44 px;
- контраст текста и controls не ниже WCAG AA;
- статус не передаётся только цветом.

### P0 — адаптивный application shell

- desktop: полный sidebar;
- tablet: navigation rail;
- mobile: top app bar и drawer;
- mobile sidebar не закрывает контент при открытии страницы;
- таблицы получают отдельное мобильное представление;
- сохраняются фильтры, выделение и позиция списка;
- один page heading вместо повторения topbar и hero;
- одна primary action на рабочую область;
- редкие и опасные действия переносятся в overflow menu.

### P1 — базовые компоненты рабочих экранов

- таблица поддерживает density, sorting, pagination и column settings;
- sticky header и закрепление ключевых колонок;
- числовые значения используют tabular numerals и правое выравнивание;
- batch selection и batch action bar;
- строка использует overflow action вместо множества кнопок;
- состояния empty, loading, error и partial-data;
- skeleton/progress для продолжительных операций;
- формы разделены на документ, финансы, контрагента, согласование и оплату;
- sticky save bar;
- dirty-state и предупреждение об изменении критических полей.

### P1 — Job Center и финансовые процессы

- общий Job Center для OCR, 1С, export, backup и bot report;
- job хранит статус, прогресс, автора, время, результат и ошибку;
- график платежей использует остаток, а не номинальную сумму;
- график разделяет «планируется» и «готово к оплате»;
- причины блокировки видны до нажатия действия;
- реестр отображает stepper состояний;
- проверка и export показывают конкретную версию и snapshot.

### P2 — productivity

- command palette `Ctrl+K`;
- context drawer без потери фильтров и позиции;
- saved views;
- role-based workspace;
- keyboard shortcuts;
- system/light/dark/high-contrast themes;
- пользовательские настройки колонок и плотности.

### Метрики готовности

- первая строка данных видна без повторного hero;
- ключевые сценарии выполняются клавиатурой;
- mobile navigation проверена на ширине 390 px;
- основные touch targets не меньше 44×44 px;
- ошибки формы имеют summary, inline error и управляемый focus;
- для критических OCR-полей видны источник и история;
- таблицы читаемы в compact и comfortable режимах.


# 8. P2 — productivity roadmap

- Job Center;
- role-based work queue;
- context drawer;
- command palette;
- keyboard shortcuts;
- cash-flow visualization;
- explainable anomaly detection;
- persistent column settings;
- user personalization.

# 9. Рекомендуемая последовательность

1. Зафиксировать новые задачи и обновить статусы старого плана.
2. SEC-01 — production settings fail-closed.
3. USER-01 — защита последнего администратора и password validators.
4. FILE-01/FILE-02 — protected media и soft-delete selectors.
5. Создать characterization-ветку финансового контура.
6. FIN-01 — canonical remaining/readiness.
7. FIN-02/FIN-03 — state machine и атомарный ledger.
8. FIN-04 — immutable snapshot и закрытие legacy export.
9. OCR-01/OCR-02.
10. ONEC-01.
11. OPS-01.
12. UI и performance — после стабилизации доменных правил.

# 10. Definition of Done для каждой задачи

- дефект воспроизведён на актуальном `main`;
- добавлен падающий characterization/regression-тест;
- выполнено минимальное точечное изменение;
- целевые тесты прошли;
- полный suite прошёл один раз в feature-ветке;
- `manage.py check` и migration check прошли;
- merge выполнен через `develop` и `main`;
- production SHA подтверждён;
- production-сценарий проверен;
- tracker обновлён фактическими commit SHA.
