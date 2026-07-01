# Quality Baseline

## Цель

Этот документ фиксирует минимальный уровень качества для проекта Project Zarya Enterprise.

Проект является Django-приложением с ERP-логикой: счета, OCR, контрагенты, реестр оплаты, график платежей, экспорт и аудит действий.

## Текущий базовый уровень

На момент введения quality baseline:

- Django-приложения расположены в корне проекта:
  - users
  - invoices
  - reports
  - ocr
  - system
  - audit
- Настройки разделены:
  - config/settings/base.py
  - config/settings/local.py
  - config/settings/production.py
- Секреты должны храниться в .env.
- .env не должен попадать в Git.
- Для примера используется .env.example.
- Для production-зависимостей используется requirements_production.txt.
- Для деплоя на Jino используется docs/JINO_DEPLOY_FROM_GITHUB.md.

## Обязательные проверки перед merge

Перед merge в develop нужно запускать:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test
```

## Минимальный CI

GitHub Actions должен проверять:

- установку зависимостей;
- Django system check;
- отсутствие забытых миграций;
- план миграций;
- запуск тестов.

## Следующие улучшения

После базового CI нужно добавить:

1. Критические тесты прав доступа.
2. Критические тесты платёжного реестра.
3. Тесты частичных оплат.
4. Тесты OCR-очереди.
5. Проверку экспорта.
6. Проверку зависимостей через pip-audit или safety.
7. Линтеры black, isort, flake8.
8. Sentry или структурированные логи ошибок.

## Что пока не делаем

На этом этапе не внедряем:

- Docker;
- Celery/Redis как обязательную инфраструктуру;
- PostgreSQL в CI;
- mypy;
- Swagger/OpenAPI.

Эти пункты нужны позже, когда будет стабилизирована бизнес-логика и появятся реальные внешние интеграции.
