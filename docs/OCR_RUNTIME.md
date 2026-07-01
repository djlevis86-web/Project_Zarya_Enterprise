# OCR Runtime

## Назначение

OCR в проекте Project Zarya Enterprise используется для распознавания текста из файлов счетов.

Приложение может:

- принимать файлы счетов;
- создавать OCR-задачи;
- хранить OCR-очередь;
- запускать команду обработки очереди.

Но для фактического OCR нужны системные зависимости.

## Обязательные зависимости

Для PDF OCR нужны Poppler utilities:

```text
pdfinfo
pdftoppm
```

Для распознавания текста нужен Tesseract OCR:

```text
tesseract
```

Также нужны языковые данные:

```text
rus
eng
```

## Диагностика

Проверить окружение можно командой:

```bash
python manage.py ocr_diagnostics
```

Если все зависимости есть, результат будет:

```text
OCR runtime: available
```

Если зависимостей нет:

```text
OCR runtime: unavailable
```

## Jino shared hosting

На текущем Jino shared hosting были проверены команды:

```bash
which pdfinfo
which pdftoppm
which tesseract
which apt
which yum
which dnf
```

Результат:

```text
NO pdfinfo
NO pdftoppm
NO tesseract
NO apt
NO yum
NO dnf
```

Это означает, что OCR нельзя полноценно выполнять прямо на этом shared hosting.

## Рекомендуемая архитектура

Jino должен выполнять:

- Django-приложение;
- загрузку счетов;
- хранение файлов;
- создание OCRJob;
- отображение статусов OCR.

OCR-worker должен выполняться отдельно там, где доступны Poppler и Tesseract:

- локальный компьютер;
- отдельный VPS;
- отдельный worker-сервер;
- внешний OCR API.

## Настройки .env

Для локального Windows-окружения можно указать:

```env
POPPLER_PATH=D:\Release-26.02.0-0\poppler-26.02.0\Library\bin
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Для Linux, если утилиты установлены в PATH:

```env
POPPLER_PATH=
TESSERACT_CMD=
```

## Правило

Если `python manage.py ocr_diagnostics` показывает `OCR runtime: unavailable`, обработку OCR запускать бессмысленно: задачи будут уходить в ошибку.
