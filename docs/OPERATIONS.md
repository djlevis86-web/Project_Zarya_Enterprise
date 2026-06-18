Адрес проекта:
http://127.0.0.1:8000/
# Project Zarya Enterprise — эксплуатационная памятка

## 1. Быстрый запуск проекта

```powershell
cd D:\Project_Zarya
.\venv\Scripts\activate
python manage.py runserver

Адрес проекта:

http://127.0.0.1:8000/
2. Основные проверки перед изменениями

Перед любой новой задачей:

cd D:\Project_Zarya
git switch develop
git status --short --branch
.\scripts\preflight_check.ps1

Расширенная проверка:

.\scripts\smoke_check.ps1
3. OCR-worker

Один проход OCR-очереди:

.\scripts\run_ocr_worker.ps1 -RunOnce

Постоянный режим:

.\scripts\run_ocr_worker.ps1 -Limit 5 -IntervalSeconds 30

Запуск через bat-файл:

.\scripts\run_ocr_worker.bat
4. Автозапуск OCR-worker

Установить задачу Windows:

.\scripts\install_ocr_worker_task.ps1 -Limit 5 -IntervalSeconds 30

Проверить статус:

.\scripts\status_ocr_worker_task.ps1

Удалить задачу:

.\scripts\uninstall_ocr_worker_task.ps1
5. Работа с Git

Новая задача:

git switch develop
git pull origin develop
git switch -c feature-short-task-name

Проверка перед commit:

.\scripts\preflight_check.ps1
.\scripts\smoke_check.ps1
git status --short --branch

Commit:

git add .
git commit -m "Short meaningful message"
git push origin feature-short-task-name:feature-short-task-name

Слияние в develop:

git switch develop
git branch safety-develop-before-task-name
git merge --no-ff feature-short-task-name -m "Merge task name into develop"
.\scripts\preflight_check.ps1
.\scripts\smoke_check.ps1
git push origin develop:develop

Слияние в main:

git switch main
git branch safety-main-before-task-name
git merge --no-ff develop -m "Merge develop task name into main"
.\scripts\preflight_check.ps1
.\scripts\smoke_check.ps1
git push origin main:main
git switch develop
6. Stable tags

Создать стабильную метку:

git switch main
git tag stable-name-YYYY-MM-DD
git push origin stable-name-YYYY-MM-DD

Посмотреть stable-метки:

git tag -l "stable-*"
7. Бэкапы

Через интерфейс:

/system/backups/

Через системную панель:

/system/

Перед крупными изменениями желательно создать бэкап БД через интерфейс.

8. Проверяемые страницы

После изменений всегда открыть:

http://127.0.0.1:8000/dashboard/
http://127.0.0.1:8000/invoices/
http://127.0.0.1:8000/invoices/ocr-queue/
http://127.0.0.1:8000/profile/
http://127.0.0.1:8000/system/
http://127.0.0.1:8000/system/backups/
9. Что уже добавлено
OCR-очередь.
Повторный OCR одного счета.
Массовый OCR выбранных счетов.
OCR-worker.
Автозапуск OCR-worker через Windows Task Scheduler.
Smoke-check проекта.
Preflight-check проекта.
Обновленный UI профиля.
Обновленный UI системных страниц.
CSS compatibility cleanup.
10. Правило безопасности

Не делать reset, force push или rebase без отдельного подтверждения.

Перед merge всегда:

git status --short --branch
.\scripts\preflight_check.ps1
.\scripts\smoke_check.ps1

'@ | Set-Content .\docs\OPERATIONS.md -Encoding UTF8


---

## 4. Проверка

```powershell id="8j4vbj"
Get-Content .\docs\OPERATIONS.md -TotalCount 30

.\scripts\preflight_check.ps1
.\scripts\smoke_check.ps1

git status --short --branch
5. Commit и push
git add docs/OPERATIONS.md

git commit -m "Add operations runbook"

git push origin feature-operations-docs:feature-operations-docs