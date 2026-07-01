# Jino Deploy From GitHub

## Цель

Рабочая папка сайта на Jino не является Git-репозиторием.

Рабочая папка сайта:

/home/users/b/bylevinskiy/domains/app.zarya35.ru

Поэтому внутри этой папки нельзя делать:

```bash
git pull origin main
```

Правильный деплой выполняется через временный clone и rsync.

---

## Полный деплой

```bash
cd /home/users/b/bylevinskiy

rm -rf deploy_tmp_Project_Zarya

git clone https://github.com/djlevis86-web/Project_Zarya_Enterprise.git deploy_tmp_Project_Zarya

cd deploy_tmp_Project_Zarya
git checkout main
git log --oneline --decorate -3

REPO_DIR="$(git rev-parse --show-toplevel)"
APP_DIR="/home/users/b/bylevinskiy/domains/app.zarya35.ru"

rsync -av \
  --exclude ".git" \
  --exclude ".env" \
  --exclude "db.sqlite3" \
  --exclude "media" \
  --exclude "public_html" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  "$REPO_DIR/" \
  "$APP_DIR/"

cd "$APP_DIR"

source ~/venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production

python manage.py check
python manage.py migrate --plan
python manage.py collectstatic --noinput

touch passenger_wsgi.py
```

---

## Проверка после деплоя

```bash
cd /home/users/b/bylevinskiy/domains/app.zarya35.ru

python manage.py check

grep -n "page-headers" static/css/app.css || true
grep -n "page-headers" public_html/static/css/app.css || true

ls -la static/css/components/page-headers.css || true
ls -la public_html/static/css/components/page-headers.css || true
```

---

## Проверка в браузере

Открыть:

https://app.zarya35.ru/static/css/app.css

Сделать Ctrl + F5.

Потом проверить страницы:

- https://app.zarya35.ru/invoices/
- https://app.zarya35.ru/invoices/payment-registry/
- https://app.zarya35.ru/invoices/payment-schedule/
- https://app.zarya35.ru/invoices/ocr-queue/

---

## Важно

collectstatic нужно запускать только из рабочей папки сайта:

```bash
cd /home/users/b/bylevinskiy/domains/app.zarya35.ru
```

Если запустить collectstatic из временного clone, статика соберётся не туда.

---

## Чего не делать

Не запускать collectstatic из:

```bash
/home/users/b/bylevinskiy/deploy_tmp_Project_Zarya
```

И не делать git pull внутри рабочей папки сайта, потому что там нет .git.
