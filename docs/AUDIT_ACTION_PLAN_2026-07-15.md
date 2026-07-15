# Project Zarya — план устранения результатов технического аудита

**Дата аудита:** 15 июля 2026 года
**Дата создания плана:** 15 июля 2026 года
**Источник:** `Project_Zarya_Audit_Report(1).md`
**Проверенная аудитом версия:** ветка `feature-responsible-invoice-workflow-v1`, коммит `dfdaf8e`

---

## 1. Назначение документа

Этот документ является рабочим трекером устранения результатов технического аудита Project Zarya.

Аудит зафиксировал:

- High: 9;
- Medium: 16;
- Low: 8;
- отдельно перечислены UI/a11y-находки `UI-01` — `UI-10`.

Аудит выполнялся не на текущем состоянии `main`. Перед исправлением каждая находка должна быть повторно воспроизведена на актуальном коде.

Находка получает статус `DONE` только после:

1. воспроизведения на актуальном коде;
2. точного изменения в отдельной ветке;
3. regression-теста;
4. полного прогона тестов в рабочей ветке;
5. merge через `develop` и `main`;
6. production-проверки фактами;
7. записи коммита и результата в этот документ.

---

## 2. Статусы

| Статус | Значение |
|---|---|
| `OPEN` | Находка зафиксирована, текущий код ещё не перепроверен |
| `CONFIRMED` | Проблема воспроизведена на актуальном `main` |
| `IN PROGRESS` | Исправление выполняется |
| `LOCAL DONE` | Исправление и тесты прошли локально |
| `RELEASED` | Изменение попало в `main` |
| `DONE` | Production-проверка выполнена |
| `NOT REPRODUCED` | На актуальном коде проблема не воспроизводится |
| `ACCEPTED RISK` | Риск принят с письменным обоснованием |

---

## 3. Общие правила

- Не изменять код только по тексту аудита.
- Сначала получать актуальный блок кода и воспроизводить проблему.
- Не смешивать независимые риски в одном большом commit.
- Не смешивать документацию и кодовое исправление.
- Полный набор тестов запускать один раз после завершения этапа в feature-ветке.
- При merge в `develop` и `main` выполнять быстрые проверки.
- Production обновляется только из `origin/main`.
- Для permission-задач проверять разрешённый и запрещённый сценарии.
- Для state-changing endpoints проверять HTTP method и CSRF.
- Для производительности добавлять query-budget test.
- Для файловых операций проверять физическую очистку и path traversal.
- Для production settings проверять отказ запуска без обязательных переменных.

---

# 4. P0 — Security & Stability Baseline

## H-01 — IDOR при добавлении комментария к чужому счёту

**Файл:** `invoices/view_modules/invoice_status_comment_views.py`
**Риск:** изменение истории чужого документа.
**Ветка:** `feature-security-stability-baseline-v1`
**Статус:** `OPEN`

Критерии:

- единый selector видимых пользователю Invoice;
- чужой документ недоступен;
- endpoint принимает только POST;
- CSRF включён;
- тесты владельца, staff и постороннего пользователя;
- запрещённый сценарий не создаёт комментарий.

---

## H-02 — обход прав загрузки для роли ANALYST

**Файлы:** `users/permissions.py`, `invoices/view_modules/invoice_upload_views.py`
**Ветка:** `feature-security-stability-baseline-v1`
**Статус:** `OPEN`

Критерии:

- upload endpoint использует `user_can_upload_invoices`;
- backend-защита не зависит от скрытия кнопки;
- ANALYST не создаёт Invoice и OCRJob;
- разрешённые роли продолжают работать;
- regression-тесты GET и POST.

---

## H-03 — изменение статуса документа через GET

**Файл:** `invoices/view_modules/invoice_status_comment_views.py`
**Ветка:** `feature-security-stability-baseline-v1`
**Статус:** `OPEN`

Критерии:

- GET не меняет статус;
- endpoint принимает только POST;
- форма содержит CSRF;
- переходы определены единым workflow service;
- запрещённые переходы отклоняются;
- `approved_by` и `approved_at` устанавливаются согласованно;
- тесты HTTP method и transition matrix.

---

## H-04 — создание и удаление backup через GET

**Файлы:** `system/views.py`, `system/templates/system/backups.html`, `system/templates/system/dashboard.html`
**Ветка:** `feature-system-backup-http-safety-v1`
**Статус:** `OPEN`

Критерии:

- create/delete только через POST;
- CSRF-защита;
- GET не изменяет файловую систему;
- явное подтверждение удаления;
- тесты GET, POST и CSRF.

---

## H-05 — production settings работают fail-open

**Файлы:** `config/settings/base.py`, `config/settings/production.py`
**Ветка:** `feature-production-security-baseline-v1`
**Статус:** `OPEN`

Критерии:

- production не запускается без `SECRET_KEY`;
- обязательные переменные не имеют insecure fallback;
- secure cookies и HTTPS redirect имеют безопасные defaults;
- определена HSTS-политика;
- настроены `AUTH_PASSWORD_VALIDATORS`;
- формы создания пароля вызывают validators;
- `check --deploy` не содержит необъяснённых предупреждений.

---

## H-06 — недостаточная защита загрузки файлов

**Файл:** `invoices/forms.py`
**Ветка:** `feature-secure-upload-validation-v1`
**Статус:** `OPEN`

Критерии:

- лимит одного файла и суммарного batch;
- reverse-proxy body limit;
- проверка сигнатур PDF/JPEG/PNG;
- ограничения PDF pages и image pixels;
- понятные ошибки повреждённых и подменённых файлов;
- тесты размера, сигнатуры и повреждённых файлов.

---

## M-02 — `PermissionDenied` используется без импорта

**Файл:** `invoices/view_modules/payment_registry_action_views.py`
**Ветка:** `feature-security-stability-baseline-v1`
**Статус:** `OPEN`

Критерии:

- permission path возвращает 403, а не `NameError`;
- regression-тест;
- blocking lint ловит `F821`.

---

## M-03 — open redirect после назначения контрагента

**Файл:** `invoices/view_modules/counterparty_assignment_views.py`
**Ветка:** `feature-security-stability-baseline-v1`
**Статус:** `OPEN`

Критерии:

- `next` проверяется через allowed hosts;
- внешний URL игнорируется;
- внутренний URL сохраняется;
- тесты safe/unsafe redirect.

---

# 5. P1 — Performance, Operations and Data Integrity

## H-07 — синхронный построчный импорт 1С

**Файлы:** `invoices/view_modules/counterparty_import_views.py`, `invoices/one_c_import_service.py`
**Ветка:** `feature-1c-background-import-v1`
**Статус:** `OPEN`

Критерии:

- HTTP request создаёт ImportJob;
- обработка идёт в background worker;
- chunks и bulk operations;
- идемпотентность и validation report;
- временный файл очищается;
- тесты на 1 000 и 10 000 синтетических строк.

---

## H-08 — N+1 в списке счетов

**Файлы:** `invoices/models.py`, `invoices/view_modules/invoice_list_views.py`, `templates/invoices/invoice_list.html`
**Ветка:** `feature-invoice-list-query-budget-v1`
**Статус:** `OPEN`

Критерии:

- оплаченная сумма аннотируется один раз;
- properties используют annotation/cache;
- число запросов не растёт линейно;
- `assertNumQueries` для пустого и заполненного списка.

---

## H-09 — backup не гарантирует консистентность и не поддерживает PostgreSQL

**Файлы:** `system/services.py`, `scripts/backup_all.ps1`, `scripts/restore_db.ps1`
**Ветка:** `feature-backup-recovery-v1`
**Статус:** `OPEN`

Критерии:

- backend определяется фактически;
- безопасный SQLite backup;
- PostgreSQL через `pg_dump`/`pg_restore`;
- checksum, retention и off-host storage;
- автоматизированный restore drill.

---

## M-01 — небезопасное имя backup-файла

**Файл:** `system/views.py`
**Ветка:** `feature-system-backup-http-safety-v1`
**Статус:** `OPEN`

Критерии:

- безопасный basename;
- `resolve()` и проверка parent;
- whitelist имени backup;
- path traversal tests на Windows и Linux.

---

## M-04 — orphan-файлы после OCR duplicate

**Файл:** `invoices/view_modules/invoice_upload_views.py`
**Ветка:** `feature-upload-storage-integrity-v1`
**Статус:** `OPEN`

Критерии:

- duplicate rollback удаляет physical media;
- cleanup работает при exception;
- storage-aware test.

---

## M-05 — race condition duplicate upload

**Ветка:** `feature-upload-storage-integrity-v1`
**Статус:** `OPEN`

Критерии:

- constraint или транзакционная гарантия;
- параллельные запросы не создают два активных документа;
- `IntegrityError` обрабатывается;
- concurrency test.

---

## M-06 — три независимых механизма авторизации

**Ветка:** `feature-central-permission-policies-v1`
**Статус:** `OPEN`

Критерии:

- матрица role × action × scope;
- object visibility в selectors;
- действия через policy functions;
- согласование `is_staff`, бизнес-ролей и model permissions;
- единая логика reports, invoices и registry.

---

## M-07 — бизнес-роль ADMIN автоматически даёт superuser

**Файл:** `users/forms.py`
**Ветка:** `feature-central-permission-policies-v1`
**Статус:** `OPEN`

Критерии:

- бизнес-роль не выдаёт superuser автоматически;
- полномочия выдаются явно;
- анализ существующих пользователей;
- remediation plan и тесты least privilege.

---

## M-08 — reports использует устаревшие статусы и другую видимость

**Файл:** `reports/services.py`
**Ветка:** `feature-reports-policy-alignment-v1`
**Статус:** `OPEN`

Критерии:

- актуальные `Invoice.STATUS_*`;
- видимость совпадает с общей policy;
- manager/superuser/staff покрыты тестами;
- несуществующий `processing` удалён.

---

## M-09 — большие страницы без пагинации

**Файл:** `invoices/view_modules/payment_registry_page_views.py`
**Ветка:** `feature-payment-pages-pagination-v1`
**Статус:** `OPEN`

Критерии:

- пагинация schedule/registry;
- validation не материализует неограниченный набор;
- экспорт независим от HTML pagination;
- тесты большой выборки.

---

## M-10 — god modules и длинные use-case функции

**Статус:** `OPEN`

Разделять постепенно после selectors, policies и regression-тестов. Большой rewrite запрещён.

---

## M-11 — дублирование export/import workflow

**Статус:** `OPEN`

Цель: общий dataset builder и независимые renderers Excel/1С.

---

## M-12 — нет структурированного логирования и error monitoring

**Ветка:** `feature-observability-baseline-v1`
**Статус:** `OPEN`

Критерии:

- Django `LOGGING`;
- удаление `print()` и `traceback.print_exc()` из production path;
- request/job correlation ID;
- redaction;
- Sentry/GlitchTip либо документированный эквивалент;
- метрики OCR и background jobs.

---

## M-13 — Celery task без production-grade failure policy

**Файл:** `ocr/tasks.py`
**Ветка:** `feature-ocr-task-reliability-v1`
**Статус:** `OPEN`

Критерии:

- retries/backoff;
- soft/hard limits;
- идемпотентность;
- транзакционная блокировка;
- exception не маскируется;
- requeue/dead-letter procedure;
- unit и integration tests.

---

## M-14 — недостаточные validators и DB constraints

**Ветка:** `feature-domain-constraints-v1`
**Статус:** `OPEN`

Критерии:

- отрицательная сумма запрещена;
- priority ограничен 1–5;
- определена уникальность ключей 1С;
- ИНН, БИК и счета валидируются;
- стратегия `ResponsiblePerson.full_name` согласована;
- data audit перед constraints.

---

## M-15 — README не соответствует Django-проекту

**Статус:** `OPEN`

Создать актуальный `README.md`; убрать Flask/SQLAlchemy из основного пути запуска.

---

## M-16 — deployment не воспроизводим полностью

**Статус:** `OPEN`

Сохранить systemd/nginx/gunicorn templates, health check, release/rollback procedure, PostgreSQL/Redis/Celery checks.

---

## QA-01 — слабое покрытие критических модулей

**Ветка:** `feature-ci-quality-gates-v1`
**Статус:** `OPEN`

Критерии:

- test settings с быстрым password hasher;
- coverage threshold не ниже baseline;
- тесты `ocr/tasks.py`, 1С import, system и export;
- CI timeout;
- coverage artifact.

---

## QA-02 — CI не блокирует типовые ошибки качества и безопасности

**Ветка:** `feature-ci-quality-gates-v1`
**Статус:** `OPEN`

Критерии:

- blocking lint минимум `F821`, `E9`, `F63`, `F7`, `F82`;
- Bandit и dependency audit;
- `check --deploy`;
- CSS syntax check;
- CI для `main`, `develop` и pull request.

---

# 6. UI, UX и доступность

## UI-01 — label не связан с полем
**Статус:** `OPEN`

## UI-02 — ошибки форм не размечены для assistive technology
**Статус:** `OPEN`

## UI-03 — отсутствуют skip link и `aria-current`
**Статус:** `OPEN`

## UI-04 — неполный focus style и повреждённое CSS-правило
**Статус:** `OPEN`

## UI-05 — отсутствует `prefers-reduced-motion`
**Статус:** `OPEN`

## UI-06 — CSS override debt
**Статус:** `OPEN`

## UI-07 — мобильные таблицы ограничены horizontal scroll
**Статус:** `OPEN`

## UI-08 — нет единого progress/status pattern
**Статус:** `OPEN`

## UI-09 — destructive actions используют browser `confirm()`
**Статус:** `OPEN`

## UI-10 — reports dashboard выбивается из дизайн-системы
**Статус:** `OPEN`

---

## 7. Примечание по Low-находкам

Аудит сообщает о восьми Low-находках, но основной отчёт не присваивает им отдельные ID `L-01` — `L-08`.

Поэтому:

- число `Low: 8` сохраняется;
- UI-находки фиксируются как `UI-01` — `UI-10`;
- отдельные `L-*` добавляются только после сопоставления raw evidence.

---

# 8. Очерёдность этапов

1. `feature-security-stability-baseline-v1`: H-01, H-02, H-03, M-02, M-03.
2. `feature-system-backup-http-safety-v1`: H-04, M-01.
3. `feature-production-security-baseline-v1`: H-05.
4. `feature-secure-upload-validation-v1`: H-06, M-04, M-05.
5. `feature-invoice-list-query-budget-v1`: H-08.
6. 1С и background jobs: H-07, M-13, затем M-12.
7. Backup/recovery: H-09.
8. CI, architecture, UI и документация: QA-01, QA-02, M-10, M-11, M-15, M-16, UI-01 — UI-10.

---

# 9. Журнал выполнения

| Дата | ID | Действие | Ветка | Коммит | Результат |
|---|---|---|---|---|---|
| 2026-07-15 | AUDIT-SETUP | Создан план устранения результатов аудита | `docs-audit-action-plan-2026-07-15-v1` | — | Документ создан |
