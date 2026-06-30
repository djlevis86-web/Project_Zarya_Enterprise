# Jino Deploy Checklist — Project Zarya Enterprise

Документ описывает подготовку и тестовую публикацию Django-проекта Project Zarya Enterprise на хостинг Jino.

---

## 1. Что уже подготовлено

В проекте уже настроено:

- production settings: config/settings/production.py
- WSGI entrypoint: config/wsgi.py
- переменные окружения через .env
- STATIC_ROOT
- MEDIA_ROOT
- WhiteNoise для static-файлов
- авторизация по e-mail
- роли пользователей
- внутренняя админка пользователей
- production smoke локально прошёл
- collectstatic локально проходит

Проверенные команды:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py migrate --plan
    python manage.py collectstatic --noinput

---

## 2. Что нельзя заливать в GitHub

Не должны попадать в репозиторий:

    .env
    db.sqlite3
    media/
    staticfiles/
    venv/
    node_modules/
    backups/
    backups_db/
    backups_media/

Эти файлы и папки закрываются через .gitignore.

---

## 3. Что нужно на хостинге

На сервере нужны:

- Python
- pip
- virtualenv / venv
- доступ к файлам проекта
- возможность создать .env
- WSGI-запуск Django-приложения

Проверка Python:

    python --version
    python3 --version

---

## 4. Какие файлы загружать

Загружать код проекта:

    analytics/
    api/
    audit/
    config/
    docs/
    invoices/
    ocr/
    reports/
    scripts/
    static/
    system/
    templates/
    users/
    manage.py
    requirements.txt
    requirements_production.txt
    .env.example

Не загружать как код:

    venv/
    node_modules/
    staticfiles/
    media/
    db.sqlite3
    .env

Если нужен тест с локальными данными, db.sqlite3 и media/ переносятся отдельно вручную.

---

## 5. .env на сервере

Создать файл .env рядом с manage.py.

Пример:

    DJANGO_SETTINGS_MODULE=config.settings.production
    SECRET_KEY=replace-with-real-secret-key
    DEBUG=False

    ALLOWED_HOSTS=your-domain.ru,www.your-domain.ru
    CSRF_TRUSTED_ORIGINS=https://your-domain.ru,https://www.your-domain.ru

    DATABASE_URL=sqlite:///db.sqlite3

    STATIC_ROOT=staticfiles
    MEDIA_ROOT=media

    SESSION_COOKIE_SECURE=False
    CSRF_COOKIE_SECURE=False
    SECURE_SSL_REDIRECT=False

    CELERY_BROKER_URL=redis://127.0.0.1:6379/0
    CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

    GITHUB_REPO=
    OCR_ENABLED=True

Для HTTPS позже можно включить:

    SESSION_COOKIE_SECURE=True
    CSRF_COOKIE_SECURE=True
    SECURE_SSL_REDIRECT=True

---

## 6. Установка зависимостей

В корне проекта:

    python -m venv venv
    source venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements_production.txt

Если production-файл окажется неполным:

    pip install -r requirements.txt

---

## 7. Проверка настроек

    export DJANGO_SETTINGS_MODULE=config.settings.production
    python manage.py check

Ожидаемый результат:

    System check identified no issues

Проверка значений:

    python manage.py shell -c "from django.conf import settings; print(settings.DEBUG); print(settings.ALLOWED_HOSTS); print(settings.STATIC_ROOT); print(settings.MEDIA_ROOT)"

---

## 8. Миграции

Если база новая:

    export DJANGO_SETTINGS_MODULE=config.settings.production
    python manage.py migrate
    python manage.py createsuperuser

Если переносится локальная база db.sqlite3:

    export DJANGO_SETTINGS_MODULE=config.settings.production
    python manage.py migrate

---

## 9. Static-файлы

Собрать static:

    export DJANGO_SETTINGS_MODULE=config.settings.production
    python manage.py collectstatic --noinput

После сборки должна появиться папка:

    staticfiles/

---

## 10. Media-файлы

Папка media/ нужна для загруженных счетов и файлов.

Для пустого тестового запуска:

    mkdir -p media

Если переносятся локальные файлы, перенести содержимое:

    D:\Project_Zarya\media

в серверную папку:

    media/

Static отдаёт WhiteNoise. Media обычно должен отдавать веб-сервер или настройки хостинга.

---

## 11. WSGI

Точка входа проекта:

    config/wsgi.py

WSGI application:

    config.wsgi:application

По умолчанию используется:

    DJANGO_SETTINGS_MODULE=config.settings.production

---

## 12. Проверка после публикации

Проверить в браузере:

    https://your-domain.ru/

Проверить:

- открывается страница входа
- есть поле E-mail
- работает вход администратора
- открывается dashboard
- открывается список счетов
- открывается загрузка счетов
- работает разграничение ролей
- static CSS подключается
- нет белой страницы без стилей

---

## 13. Smoke через Django Client

На сервере:

    export DJANGO_SETTINGS_MODULE=config.settings.production

    python manage.py shell -c "from django.test import Client; from django.urls import reverse; c=Client(HTTP_HOST='your-domain.ru'); c.raise_request_exception=False; r=c.get(reverse('login'), HTTP_HOST='your-domain.ru'); text=r.content.decode('utf-8', errors='ignore'); print('login status:', r.status_code); print('has login page:', 'Вход в систему' in text); print('has email label:', 'E-mail' in text)"

Ожидаем:

    login status: 200
    has login page: True
    has email label: True

---

## 14. Возможные ограничения

OCR может требовать системные зависимости:

- Tesseract
- Poppler
- PDF/Image libraries

Если на хостинге нет системных пакетов, OCR может работать ограниченно.

Celery и Redis для базового тестового запуска сайта не обязательны.

Media-файлы нужно проверить отдельно, потому что они обычно отдаются не WhiteNoise, а веб-сервером.

---

## 15. Минимальный порядок деплоя

    git pull origin main
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements_production.txt
    cp .env.example .env
    nano .env
    export DJANGO_SETTINGS_MODULE=config.settings.production
    python manage.py check
    python manage.py migrate
    python manage.py collectstatic --noinput
    python manage.py createsuperuser

После этого настроить WSGI-приложение на:

    config.wsgi:application

---

## 16. Контрольный чек

    [ ] .env создан
    [ ] SECRET_KEY заменён
    [ ] DEBUG=False
    [ ] ALLOWED_HOSTS указан
    [ ] CSRF_TRUSTED_ORIGINS указан для HTTPS
    [ ] python manage.py check проходит
    [ ] миграции применены
    [ ] collectstatic проходит
    [ ] страница входа открывается
    [ ] вход администратора работает
    [ ] роли пользователей работают
    [ ] static отображается
    [ ] media проверена отдельно
