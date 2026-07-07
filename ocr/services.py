import os
import math
import re
from decimal import Decimal, InvalidOperation

import pytesseract

from PIL import Image
from PIL import ImageFilter
from PIL import ImageOps
from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError
from pytesseract import TesseractNotFoundError
from datetime import date


TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    "",
).strip()

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


POPPLER_PATH = os.getenv(
    "POPPLER_PATH",
    "",
).strip() or None



MAX_OCR_IMAGE_PIXELS = int(
    os.getenv(
        "MAX_OCR_IMAGE_PIXELS",
        "12000000"
    )
)

MAX_OCR_IMAGE_SIDE = int(
    os.getenv(
        "MAX_OCR_IMAGE_SIDE",
        "3200"
    )
)

OCR_TESSERACT_TIMEOUT = int(
    os.getenv(
        "OCR_TESSERACT_TIMEOUT",
        "25"
    )
)

OCR_PDF_DPI_VARIANTS = [
    180,
    150,
    120,
]

OCR_PDF_MAX_PAGES = int(
    os.getenv(
        "OCR_PDF_MAX_PAGES",
        "3"
    )
)


OCR_MAX_TESSERACT_CALLS = int(
    os.getenv(
        "OCR_MAX_TESSERACT_CALLS",
        "8"
    )
)

Image.MAX_IMAGE_PIXELS = max(
    Image.MAX_IMAGE_PIXELS or 0,
    MAX_OCR_IMAGE_PIXELS * 4
)


def get_image_resample_filter():
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS

    return Image.LANCZOS


def safe_prepare_image_for_ocr(image):
    if not image:
        return image

    width, height = image.size
    pixels = width * height

    if (
        pixels > MAX_OCR_IMAGE_PIXELS
        or width > MAX_OCR_IMAGE_SIDE
        or height > MAX_OCR_IMAGE_SIDE
    ):
        scale = min(
            MAX_OCR_IMAGE_SIDE / max(width, 1),
            MAX_OCR_IMAGE_SIDE / max(height, 1),
            math.sqrt(MAX_OCR_IMAGE_PIXELS / max(pixels, 1)),
        )

        scale = min(
            scale,
            1
        )

        new_width = max(
            1,
            int(width * scale)
        )

        new_height = max(
            1,
            int(height * scale)
        )

        image.thumbnail(
            (
                new_width,
                new_height,
            ),
            resample=get_image_resample_filter()
        )
    else:
        image.load()

    if image.mode not in [
        "RGB",
        "L",
    ]:
        image = image.convert(
            "RGB"
        )

    return image


def get_pdf_page_count(pdf_path):
    try:
        info = pdfinfo_from_path(
            pdf_path,
            **get_poppler_kwargs(),
        )

        return int(
            info.get(
                "Pages",
                1
            )
        )

    except PDFInfoNotInstalledError as error:
        raise RuntimeError(
            "Poppler не установлен или не найден в PATH. "
            "Для OCR PDF нужны утилиты pdfinfo/pdftoppm. "
            "На Windows укажи POPPLER_PATH в .env. "
            "На Linux установи poppler-utils или запускай OCR-worker там, где Poppler доступен."
        ) from error

    except Exception:
        return 1


def convert_pdf_page(pdf_path, dpi, page_number):
    try:
        pages = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
            thread_count=1,
            grayscale=True,
            **get_poppler_kwargs(),
        )

        if not pages:
            return None

        return safe_prepare_image_for_ocr(
            pages[0]
        )

    except PDFInfoNotInstalledError as error:
        raise RuntimeError(
            "Poppler не установлен или не найден в PATH. "
            "Для OCR PDF нужны утилиты pdfinfo/pdftoppm. "
            "На Windows укажи POPPLER_PATH в .env. "
            "На Linux установи poppler-utils или запускай OCR-worker там, где Poppler доступен."
        ) from error

def get_poppler_kwargs():
    if not POPPLER_PATH:
        return {}

    return {
        "poppler_path": POPPLER_PATH,
    }


def convert_pdf_pages(pdf_path, dpi):
    page_count = min(
        get_pdf_page_count(
            pdf_path
        ),
        OCR_PDF_MAX_PAGES
    )

    pages = []

    for page_number in range(
        1,
        page_count + 1
    ):
        page = convert_pdf_page(
            pdf_path,
            dpi=dpi,
            page_number=page_number
        )

        if page:
            pages.append(
                page
            )

    return pages


def is_ocr_timeout_error(error):
    message = str(
        error
    ).lower()

    return (
        "timeout" in message
        or "timed out" in message
        or "таймаут" in message
        or "превысил лимит времени" in message
    )


def image_to_text(image, config):
    try:
        image = safe_prepare_image_for_ocr(
            image
        )

        return pytesseract.image_to_string(
            image,
            lang="rus+eng",
            config=config,
            timeout=OCR_TESSERACT_TIMEOUT,
        )

    except TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR не установлен или не найден в PATH. "
            "На Windows укажи TESSERACT_CMD в .env. "
            "На Linux установи tesseract и языковые пакеты rus/eng "
            "или запускай OCR-worker там, где Tesseract доступен."
        ) from error

    except RuntimeError as error:
        if is_ocr_timeout_error(error):
            raise RuntimeError(
                "OCR превысил лимит времени на распознавание. "
                "Файл сохранен, но OCR нужно повторить отдельно или уменьшить качество изображения."
            ) from error

        raise


MONTH_FIXES = {
    'maa': 'мая',
    'may': 'мая',
    'man': 'мая',
    'map': 'марта',
    'mapta': 'марта',
    'января': 'января',
    'февраля': 'февраля',
    'марта': 'марта',
    'апреля': 'апреля',
    'мая': 'мая',
    'июня': 'июня',
    'июля': 'июля',
    'августа': 'августа',
    'сентября': 'сентября',
    'октября': 'октября',
    'ноября': 'ноября',
    'декабря': 'декабря',
}


BAD_VENDOR_WORDS = [
    'ОПЛАТА ПО',
    'НАЗНАЧЕНИЕ ПЛАТЕЖА',
    'РЕАЛИЗАЦИИ ТОВАРОВ',
    'ТОВАРОВ И УСЛУГ',

    'БАНК СГБ',
    'СБЕРБАНК',
    'ПАО БАНК',
    'АО БАНК',
    'БАНК ПОЛУЧАТЕЛЯ',
    'СЧЕТ ПОЛУЧАТЕЛЯ',
    'КОРРЕСПОНДЕНТСКИЙ',
    'ПОЛУЧАТЕ',

    'ПЛАТЕЖ',
    'ПЛАТЕЖНОЕ',

    'СЧЕТ №',
    'СЧЁТ №',
    'СЧЕТ НА ОПЛАТУ',
    'СЧЁТ НА ОПЛАТУ',

    'ЗАКАЗЧИК',
    'ПОКУПАТЕЛЬ',
    'КОМУ',

    'ОАО ЗАРЯ',
]

VENDOR_STOP_PATTERNS = [
    r'\bИНН\b',
    r'\bКПП\b',
    r'\bОГРН\b',
    r'\bАдрес\b',
    r'\bТелефон\b',
    r'\bТел\b',
    r'\bтел\b',
    r'\be-mail\b',
    r'\bemail\b',

    r'\bр\s*/\s*с\b',
    r'\bр\.?\s*с\.?\b',
    r'\bр\.?\s*сч\.?\b',
    r'\bрасчетный\s+счет\b',

    r'\bБИК\b',
    r'\bБанк\b',
    r'\bк\s*/\s*с\b',
    r'\bкорр\.?\s*счет\b',

    r'\bСч\.?\s*№',
    r'\bСч[её]т\s*№',
    r'\bСч[её]т\s+на\s+оплату\b',

    r'\bCu\.?\s*№',
    r'\bI\s+Cu\.?\s*№',
    r'\bI\s+Сч\.?\s*№',
    r'\bI\s+Счет\b',
]


def normalize_ocr_text(text):

    if not text:
        return ''

    text = str(text)


    replacements = {
        'AHH': 'ИНН',
        'UHH': 'ИНН',
        'ИННН': 'ИНН',
        'KПП': 'КПП',
        'КППП': 'КПП',
        'OOO': 'ООО',
        'OОO': 'ООО',
        'ОOО': 'ООО',
        'OAO': 'ОАО',
        'AO ': 'АО ',
        'СЧЕТ HA': 'СЧЕТ НА',
        'Счет Ha': 'Счет на',
        'счет Ha': 'счет на',
        'Ne': '№',
        'No': '№',
        'N°': '№',
        '№ ': '№ ',
        '|': 'I',
        '“': '"',
        '”': '"',
        '„': '"',
        '«': '"',
        '»': '"',
        'Поётавщик': 'Поставщик',
        'Поставжик': 'Поставщик',
        'Поставшик': 'Поставщик',
        'Индинидуапьный': 'Индивидуальный',
        'Индинидуальный': 'Индивидуальный',
        'Индивидуапьный': 'Индивидуальный',
        'Рредприниматель': 'Предприниматель',
        'предпринимагель': 'предприниматель',
        'предпринимапель': 'предприниматель',
        'TK APBET': 'ТК АРВЕТ',
        'TK АРВЕТ': 'ТК АРВЕТ',
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new
        )

    text = re.sub(
        r'[^\S\r\n]+',
        ' ',
        text
    )

    text = re.sub(
        r'\n+',
        '\n',
        text
    )

    return text.strip()


def preprocess_image(image):

    image = image.convert(
        'L'
    )

    image = ImageOps.autocontrast(
        image
    )

    image = image.filter(
        ImageFilter.MedianFilter(
            size=3
        )
    )

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


def preprocess_image_hard(image):

    image = image.convert(
        'L'
    )

    image = ImageOps.autocontrast(
        image
    )

    image = image.filter(
        ImageFilter.MedianFilter(
            size=5
        )
    )

    image = image.point(
        lambda x: 255 if x > 155 else 0,
        mode='1'
    )

    image = image.convert(
        'L'
    )

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


def ocr_score(text):

    if not text:
        return 0

    text_upper = text.upper()

    score = 0

    keywords = [
        'СЧЕТ-ФАКТУРА',
        'СЧЁТ-ФАКТУРА',
        'ПРОДАВЕЦ',
        'ПОКУПАТЕЛЬ',
        'ДОКУМЕНТ ОБ ОТГРУЗКЕ',
        'ГРУЗООТПРАВИТЕЛЬ',
        'ГРУЗОПОЛУЧАТЕЛЬ',
        'СЧЕТ',
        'СЧЁТ',
        'УПД',
        'УНИВЕРСАЛЬНЫЙ',
        'ПЕРЕДАТОЧНЫЙ',
        'ОПЛАТ',
        'ПОСТАВЩИК',
        'ИСПОЛНИТЕЛЬ',
        'ИНН',
        'КПП',
        'ИТОГО',
        'ВСЕГО',
        'СУММА',
    ]

    for keyword in keywords:

        if keyword in text_upper:

            score += 10

    score += min(
        len(text) // 100,
        30
    )

    return score


def extract_text_from_pdf(pdf_path):
    variants = []
    tesseract_calls = 0

    page_count = min(
        get_pdf_page_count(
            pdf_path
        ),
        OCR_PDF_MAX_PAGES
    )

    configs_by_dpi = {
        180: [
            "--oem 3 --psm 3",
            "--oem 3 --psm 4",
            "--oem 3 --psm 11",
        ],
        150: [
            "--oem 3 --psm 3",
            "--oem 3 --psm 6",
        ],
        120: [
            "--oem 3 --psm 3",
            "--oem 3 --psm 6",
        ],
    }

    for dpi in OCR_PDF_DPI_VARIANTS:
        configs = configs_by_dpi.get(
            dpi,
            [
                "--oem 3 --psm 3",
            ]
        )

        texts_by_config = {
            config: ''
            for config in configs
        }

        for page_number in range(
            1,
            page_count + 1
        ):
            if tesseract_calls >= OCR_MAX_TESSERACT_CALLS:
                break

            page = convert_pdf_page(
                pdf_path,
                dpi=dpi,
                page_number=page_number
            )

            if not page:
                continue

            for config in configs:
                if tesseract_calls >= OCR_MAX_TESSERACT_CALLS:
                    break

                try:
                    tesseract_calls += 1

                    prepared_page = preprocess_image(
                        page.copy()
                    )

                    page_text = image_to_text(
                        prepared_page,
                        config=config,
                    )

                    texts_by_config[config] += page_text + '\n'

                except Exception as error:
                    if is_ocr_timeout_error(error):
                        raise RuntimeError(
                            "OCR остановлен по таймауту Tesseract. "
                            "Файл сохранен, но автоматическое распознавание прервано, "
                            "чтобы не зависал OCR-worker."
                        ) from error

                    continue

        for config_text in texts_by_config.values():
            normalized = normalize_ocr_text(
                config_text
            )

            if normalized:
                variants.append(
                    normalized
                )

        if variants:
            best_text = max(
                variants,
                key=ocr_score
            )

            if ocr_score(
                best_text
            ) >= 85:
                return normalize_ocr_text(
                    best_text
                )

        if tesseract_calls >= OCR_MAX_TESSERACT_CALLS:
            break

    if not variants:
        return ''

    best_text = max(
        variants,
        key=ocr_score
    )

    return normalize_ocr_text(
        best_text
    )

def extract_text_from_pdf_hard(pdf_path):
    return extract_text_from_pdf(
        pdf_path
    )


def extract_text_from_pdf_light(pdf_path):
    variants = []

    for dpi in [
        90,
        100,
        110,
    ]:
        try:
            page = convert_pdf_page(
                pdf_path,
                dpi=dpi,
                page_number=1,
            )
        except Exception:
            continue

        if not page:
            continue

        for config in [
            "--oem 3 --psm 11",
        ]:
            try:
                prepared_page = preprocess_image(
                    page.copy()
                )

                page_text = image_to_text(
                    prepared_page,
                    config=config,
                )

                normalized = normalize_ocr_text(
                    page_text
                )

                if normalized:
                    variants.append(
                        normalized
                    )

            except Exception:
                continue

    if not variants:
        return ""

    best_text = max(
        variants,
        key=ocr_score,
    )

    return normalize_ocr_text(
        best_text
    )


def extract_text_from_image(image_path):
    variants = []

    configs = [
        "--oem 3 --psm 12",
        "--oem 3 --psm 3",
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
    ]

    preprocessors = [
        preprocess_image,
        preprocess_image_hard,
    ]

    with Image.open(
        image_path
    ) as image:
        try:
            image.draft(
                "RGB",
                (
                    MAX_OCR_IMAGE_SIDE,
                    MAX_OCR_IMAGE_SIDE,
                )
            )
        except Exception:
            pass

        image = safe_prepare_image_for_ocr(
            image
        )

        base_image = image.copy()

    for config in configs:
        for preprocessor in preprocessors:
            try:
                prepared_image = preprocessor(
                    base_image.copy()
                )

                text = image_to_text(
                    prepared_image,
                    config=config,
                )

                normalized = normalize_ocr_text(
                    text
                )

                if normalized:
                    variants.append(
                        normalized
                    )

                if variants:
                    best_text = max(
                        variants,
                        key=ocr_score
                    )

                    if ocr_score(
                        best_text
                    ) >= 85:
                        return normalize_ocr_text(
                            best_text
                        )

            except Exception as error:
                if is_ocr_timeout_error(
                    error
                ):
                    continue

                continue

    if not variants:
        return ''

    best_text = max(
        variants,
        key=ocr_score
    )

    return normalize_ocr_text(
        best_text
    )


def clean_invoice_number(value):

    if not value:

        return None

    value = str(value)

    value = value.replace(
        "№",
        ""
    )

    value = value.replace(
        "N",
        ""
    )

    value = value.replace(
        "n",
        ""
    )

    value = value.replace(
        "\\u00a0",
        " "
    )

    value = value.replace(
        "\u00a0",
        " "
    )

    value = value.strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    value = re.sub(
        r"[^0-9A-Za-zА-Яа-яЁё.\-/ ]",
        "",
        value
    )

    value = value.strip(
        " .,-/"
    )

    if not value:

        return None

    if len(value) > 40:

        value = value[:40].strip()

    return value


def parse_invoice_number(text):

    if not text:

        return None

    text = str(text)

    patterns = [

        r"Счет-фактура\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",
        r"Сч[её]т-фактура\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",
        r"Универсальн\w*\s+Счет-фактура\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",
        r"Универсальн\w*\s+Сч[её]т-фактура\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",
        r"Документ\s+об\s+отгрузке.*?№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",

        r"УПД\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",
        r"УПД\s*№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",
        r"Универсальн\w*\s+передаточн\w*\s+документ\w*\s*№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",
        r"Документ\s+об\s+отгрузке\s*№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",

        r"Сч[её]т\s+на\s+оплату\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",

        r"СЧЕТ\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",

        r"СЧЁТ\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",

        r"Сч[её]т\s*№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",

        r"Сч[её]т\s+на\s+оплату\s*№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",

        r"Сч[её]т\s*№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",

        r"№\s*(.+?)\s+от\s+\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}",

        r"№\s*(.+?)\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{4}",

        r"заказу\s+клиента\s*№?\s*([A-Za-zА-Яа-яЁё0-9.\-/ ]+)",

        r"реализации\s+товаров\s+и\s+услуг\s*№\s*([A-Za-zА-Яа-яЁё0-9.\-/ ]+)",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if not match:

            continue

        number = clean_invoice_number(
            match.group(1)
        )

        if number:

            return number

    return None



def normalize_invoice_date(value):

    if not value:
        return None

    value = str(value).strip()

    value = value.replace(
        ' г.',
        ''
    )

    value = value.replace(
        ' г',
        ''
    )

    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    parts = value.split()

    if len(parts) >= 3:

        day = parts[0]
        month = parts[1].lower()
        year = parts[2]

        month = MONTH_FIXES.get(
            month,
            month
        )

        return f'{day} {month} {year}'

    return value


def parse_invoice_date(text):

    patterns = [

        r'от\s+(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4})',

        r'от\s+(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}\s*г\.?)',

        r'№\s*[A-Za-zА-Яа-я0-9\-\/]+\s*от\s*(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4})',

        r'от\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return normalize_invoice_date(
                match.group(1)
            )

    return None


def clean_vendor(value):

    if not value:
        return None

    value = str(value)

    value = value.replace(
        '\n',
        ' '
    )

    replacements = {
        'OOO': 'ООО',
        'OОO': 'ООО',
        'ОOО': 'ООО',
        'OAO': 'ОАО',
        'AO ': 'АО ',
        'CEBEP-BET': 'СЕВЕР-ВЕТ',
        'Общество с ограниченной ответственностью': 'ООО',
        'общество с ограниченной ответственностью': 'ООО',
        '"': '',
        '«': '',
        '»': '',
        '“': '',
        '”': '',
    }

    for old, new in replacements.items():

        value = value.replace(
            old,
            new
        )

    for pattern in VENDOR_STOP_PATTERNS:

        value = re.split(
            pattern,
            value,
            maxsplit=1,
            flags=re.IGNORECASE
        )[0]

    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    value = value.strip(
        ' ,.;:-—–'
    )

    value = re.sub(
        r'\bI$',
        '',
        value
    ).strip()

    if not value:

        return None

    upper_value = value.upper()

    for bad_word in BAD_VENDOR_WORDS:

        if bad_word in upper_value:

            return None

    if upper_value in [
        'ЗАРЯ',
        'ОАО ЗАРЯ',
    ]:

        return None

    if re.search(
        r'(СБЕРБАНК|БАНК|ПОЛУЧАТЕ)',
        upper_value
    ):

        return None

    if re.search(
        r'^СЧ[ЕЁ]Т\s*№',
        upper_value
    ):

        return None

    if re.search(
        r'^СЧ[ЕЁ]Т\s+НА\s+ОПЛАТУ',
        upper_value
    ):

        return None

    if re.search(
        r'^(ООО|АО|ОАО|ПАО)\s+[A-ZА-ЯЁa-zа-яё]$',
        value,
        re.IGNORECASE
    ):

        return None

    digits = re.findall(
        r'\d',
        value
    )

    if len(digits) >= 9:

        return None

    if len(value) < 3:

        return None

    return value

def extract_vendor_name_from_candidate(candidate):

    if not candidate:
        return None

    candidate = str(candidate)

    candidate = candidate.replace(
        'OOO',
        'ООО'
    )

    candidate = candidate.replace(
        'OОO',
        'ООО'
    )

    candidate = candidate.replace(
        'ОOО',
        'ООО'
    )

    candidate = candidate.replace(
        'OAO',
        'ОАО'
    )

    candidate = candidate.replace(
        'CEBEP-BET',
        'СЕВЕР-ВЕТ'
    )

    candidate = candidate.replace(
        'TK APBET',
        'ТК АРВЕТ'
    )

    candidate = candidate.replace(
        'TK АРВЕТ',
        'ТК АРВЕТ'
    )

    candidate = candidate.replace(
        'Поётавщик',
        'Поставщик'
    )

    candidate = candidate.replace(
        'Поставжик',
        'Поставщик'
    )

    candidate = candidate.replace(
        'Индинидуапьный',
        'Индивидуальный'
    )

    candidate = candidate.replace(
        'Индинидуальный',
        'Индивидуальный'
    )

    candidate = candidate.replace(
        'Индивидуапьный',
        'Индивидуальный'
    )

    patterns = [

        r'((?:ООО|ОАО|АО|ПАО)\s*"?[А-ЯA-ZЁ0-9][А-Яа-яA-Za-zЁё0-9\s\-.]+)"?',

        r'(ИП\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,3})',

        r'(Общество\s+с\s+ограниченной\s+ответственностью\s*"?[А-ЯA-ZЁ0-9][А-Яа-яA-Za-zЁё0-9\s\-.]+)"?',

        r'(Индивидуальн\w*\s+предприним\w*\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,3})',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            candidate,
            re.IGNORECASE
        )

        if match:

            vendor = clean_vendor(
                match.group(1)
            )

            if vendor:

                return vendor

    return clean_vendor(
        candidate
    )

def parse_vendor(text):

    def finish_vendor(candidate):

        vendor = extract_vendor_name_from_candidate(
            candidate
        )

        if not vendor:

            return None

        vendor = vendor.replace(
            'Общество с ограниченной ответственностью',
            'ООО'
        )

        vendor = vendor.replace(
            'общество с ограниченной ответственностью',
            'ООО'
        )

        vendor = re.sub(
            r'\s+',
            ' ',
            vendor
        ).strip()

        return vendor

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    strong_markers = [
        'Исполнитель',
        'Поставщик',
        'Продавец',
    ]

    forbidden_next_lines = [
        'Заказчик',
        'Покупатель',
        'Кому',
        'Счет №',
        'Сч. №',
        'Счёт №',
        'Банк',
        'Банк получателя',
        'Получатель',
    ]

    for index, line in enumerate(lines):

        for marker in strong_markers:

            match = re.search(
                rf'\b{marker}\b\s*[:\-]?\s*(.*)$',
                line,
                re.IGNORECASE
            )

            if not match:

                continue

            current_candidate = match.group(1).strip()

            vendor = finish_vendor(
                current_candidate
            )

            if vendor:

                return vendor

            if index + 1 < len(lines):

                next_line = lines[index + 1].strip()

                next_line_upper = next_line.upper()

                blocked = False

                for bad_start in forbidden_next_lines:

                    if next_line_upper.startswith(
                        bad_start.upper()
                    ):

                        blocked = True

                if not blocked:

                    vendor = finish_vendor(
                        next_line
                    )

                    if vendor:

                        return vendor

    for index, line in enumerate(lines):

        match = re.search(
            r'\bПолучатель\b\s*[:\-]?\s*(.*)$',
            line,
            re.IGNORECASE
        )

        if not match:

            continue

        candidate = match.group(1).strip()

        vendor = finish_vendor(
            candidate
        )

        if vendor:

            return vendor

        if index + 1 < len(lines):

            next_line = lines[index + 1].strip()

            if re.search(
                r'ООО|ОАО|АО|ПАО|Индивидуальн|Общество',
                next_line,
                re.IGNORECASE
            ):

                vendor = finish_vendor(
                    next_line
                )

                if vendor:

                    return vendor

    patterns = [

        r'(ИП\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,3})',

        r'((?:ООО|ОАО|АО|ПАО)\s*"?[А-ЯA-ZЁ0-9][А-Яа-яA-Za-zЁё0-9\s\-.]+)"?',

        r'(Общество\s+с\s+ограниченной\s+ответственностью\s*"?[А-ЯA-ZЁ0-9][А-Яа-яA-Za-zЁё0-9\s\-.]+)"?',

        r'(Индивидуальн\w*\s+предприним\w*\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,3})',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            vendor = finish_vendor(
                match.group(1)
            )

            if vendor:

                return vendor

    return None


def normalize_amount(value):

    if not value:
        return None

    value = str(value)

    value = value.replace(
        '\u00a0',
        ' '
    )

    value = value.replace(
        "'",
        ''
    )

    value = value.replace(
        ' ',
        ''
    )

    value = value.replace(
        ',',
        '.'
    )

    value = re.sub(
        r'[^0-9.]',
        '',
        value
    )

    match = re.search(
        r'(\d+\.\d{2})',
        value
    )

    if match:

        return match.group(1)

    return None



def normalize_ocr_money_token_for_total_selection(value):
    if value is None:
        return None

    value = str(value)
    value = value.replace('\u00a0', ' ')
    value = value.replace(' ', '')
    value = value.replace('$', '')
    value = value.replace('[', '')
    value = value.replace(']', '')
    value = value.replace(',', '.')
    value = value.strip(' .,:;')

    if not value:
        return None

    try:
        amount = Decimal(value).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if amount <= 0:
        return None

    return format(amount, 'f')


def get_money_tokens_from_text(value):
    if not value:
        return []

    value = str(value).replace('\u00a0', ' ')

    money_pattern = re.compile(
        r'(?<!\d)(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[,.]\d{2})(?!\d)'
    )

    result = []

    for match in money_pattern.finditer(value):
        normalized = normalize_ocr_money_token_for_total_selection(
            match.group(0)
        )

        if normalized:
            result.append(normalized)

    return result


def get_line_with_keyword(text, keyword):
    keyword_lower = keyword.lower()

    for line in str(text).splitlines():
        if keyword_lower in line.lower():
            pos = line.lower().find(keyword_lower)
            return line[pos:]

    pos = str(text).lower().find(keyword_lower)

    if pos < 0:
        return ''

    return str(text)[pos:pos + 260]


def get_first_money_after_phrase(text, phrase):
    pattern = re.compile(
        phrase + r'.{0,120}',
        re.IGNORECASE | re.DOTALL
    )

    match = pattern.search(text)

    if not match:
        return None

    amounts = get_money_tokens_from_text(
        match.group(0)
    )

    if not amounts:
        return None

    return amounts[0]


def get_last_money_on_keyword_line(text, keyword):
    line = get_line_with_keyword(
        text,
        keyword
    )

    if not line:
        return None

    amounts = get_money_tokens_from_text(
        line
    )

    if not amounts:
        return None

    return amounts[-1]


def parse_preferred_total_amount(text):
    if not text:
        return None

    normalized_text = str(text)
    normalized_text = normalized_text.replace('\u00a0', ' ')

    # 1. Самые надежные итоговые формулировки.
    for phrase in [
        r'Итого\s+с\s+НДС\s*[:\-]?\s*',
        r'Итого\s+к\s+оплате\s*[:\-]?\s*',
    ]:
        amount = get_first_money_after_phrase(
            normalized_text,
            phrase
        )

        if amount:
            return amount

    # 2. УПД / счет-фактура: в строке "Всего к оплате" последняя сумма — с НДС.
    amount = get_last_money_on_keyword_line(
        normalized_text,
        'Всего к оплате'
    )

    if amount:
        return amount

    # 3. Стандартный счет: итоговая строка может содержать несколько колонок.
    # Берем последнюю сумму в строке "Итого Руб" / "Итого:".
    for keyword in [
        'Итого Руб',
        'Итого:',
        'Итого'
    ]:
        amount = get_last_money_on_keyword_line(
            normalized_text,
            keyword
        )

        if amount:
            return amount

    # 4. Фраза "Всего наименований ..., на сумму ..." — сумма счета.
    amount = get_first_money_after_phrase(
        normalized_text,
        r'Всего\s+наименований.*?на\s+сумму\s*'
    )

    if amount:
        return amount

    return None

def parse_amount(text):

    if not text:

        return None

    text = str(text)

    preferred_total_amount = parse_preferred_total_amount(
        text
    )

    if preferred_total_amount:
        return preferred_total_amount

    text = text.replace(
        '\\u00a0',
        ' '
    )

    text = text.replace(
        '\u00a0',
        ' '
    )

    text = text.replace(
        '‚',
        ','
    )

    def prepare_money_value(value):

        if not value:

            return None

        value = str(value)

        value = value.replace(
            "'",
            ""
        )

        value = value.replace(
            " ",
            ""
        )

        value = value.replace(
            "\\u00a0",
            ""
        )

        value = value.replace(
            "\u00a0",
            ""
        )

        value = value.replace(
            "‚",
            ","
        )

        value = re.sub(
            r'(?<=\d)-(?=\d{2}$)',
            '.',
            value
        )

        return normalize_amount(
            value
        )

    money = (
        r"(\d{1,3}(?:[\s\u00a0']\d{3})+[,.]\d{2}"
        r"|\d{4,}[,.\-]\d{2}"
        r"|\d+[,.]\d{2})"
    )

    patterns = [

        rf'Всего\s+к\s+оплате[:\s]*{money}',

        rf'Итого\s+к\s+оплате[:\s]*{money}',

        rf'Итого\s+с\s+НДС[:\s]*{money}',

        rf'Итого\s+с\s+Hic[;:\s]*{money}',

        rf'Всего[:\s]*{money}',

        rf'Итого[:\s]*{money}',

        rf'на\s+сумму\s+{money}',

        rf'сумму\s+{money}\s*руб',

    ]

    for pattern in patterns:

        matches = list(
            re.finditer(
                pattern,
                text,
                re.IGNORECASE
            )
        )

        if not matches:

            continue

        for match in reversed(matches):

            amount = prepare_money_value(
                match.group(1)
            )

            if amount:

                return amount

    candidates = re.findall(
        money,
        text
    )

    values = []

    for candidate in candidates:

        amount = prepare_money_value(
            candidate
        )

        if not amount:

            continue

        try:

            numeric = float(
                amount
            )

        except ValueError:

            continue

        if numeric <= 0:

            continue

        if numeric > 1_000_000_000:

            continue

        values.append(
            numeric
        )

    if values:

        return f'{max(values):.2f}'

    return None



def extract_inn(text):

    match = re.search(
        r'ИНН\s*[:№]?\s*(\d{10,12})',
        text,
        re.IGNORECASE
    )

    if match:

        return match.group(1)

    return None


def extract_kpp(text):

    match = re.search(
        r'КПП\s*[:№]?\s*(\d{9})',
        text,
        re.IGNORECASE
    )

    if match:

        return match.group(1)

    return None



def detect_document_type(text):
    normalized = normalize_ocr_text(text or '').lower()

    if not normalized:
        return 'invoice'

    compact = re.sub(
        r'[\W_]+',
        '',
        normalized,
        flags=re.UNICODE
    )

    upd_markers = (
        'упд',
        'универсальный передаточный документ',
        'универсальный передаточный',
        'документ об отгрузке',
        'передаточный документ',
    )

    for marker in upd_markers:
        if marker in normalized:
            return 'upd'

    waybill_markers = (
        'товарная накладная',
        'торг-12',
        'торг 12',
        'форма торг',
    )

    for marker in waybill_markers:
        if marker in normalized:
            return 'waybill'

    payment_document_markers = (
        'платежный документ',
        'платёжный документ',
        'извещение на оплату жку',
        'извещение на оплату',
        'квитанция',
        'исполнитель услуг',
        'получатель платежа',
        'данные по оплате',
    )

    for marker in payment_document_markers:
        if marker in normalized:
            return 'payment_document'

    if (
        'извещениенаоплату' in compact
        and (
            'жку' in compact
            or 'квитанция' in compact
        )
    ):
        return 'payment_document'

    invoice_markers = (
        'счет на оплату',
        'счёт на оплату',
        'счет №',
        'счёт №',
        'сч. №',
        'сч №',
        'счет-фактура',
        'счёт-фактура',
        'заказу клиента',
        'оплата данного счета',
        'оплата данного счёта',
        'счет действителен',
        'счёт действителен',
    )

    for marker in invoice_markers:
        if marker in normalized:
            return 'invoice'

    invoice_compact_markers = (
        'счетнаоплату',
        'счётнаоплату',
        'счетфактура',
        'счётфактура',
    )

    for marker in invoice_compact_markers:
        if marker in compact:
            return 'invoice'

    noisy_invoice_patterns = (
        r'\bна\s+оплату\s*№\s*[a-zа-яё0-9\-_/]+\s+от\s+\d{1,2}\s+[а-яё]+\s+\d{4}',
        r'\bоплату\s*№\s*[a-zа-яё0-9\-_/]+\s+от\s+\d{1,2}\s+[а-яё]+\s+\d{4}',
    )

    for pattern in noisy_invoice_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            return 'invoice'

    if re.search(
        r'(^|\s)[il1]\s*сч\.?\s*№?',
        normalized,
        re.IGNORECASE
    ):
        return 'invoice'

    return 'unknown'

def parse_document_date_value(value):
    if not value:
        return None

    value = str(value).strip().lower()

    month_map = {
        'января': 1,
        'январь': 1,
        'февраля': 2,
        'февраль': 2,
        'марта': 3,
        'март': 3,
        'апреля': 4,
        'апрель': 4,
        'мая': 5,
        'май': 5,
        'июня': 6,
        'июнь': 6,
        'июля': 7,
        'июль': 7,
        'августа': 8,
        'август': 8,
        'сентября': 9,
        'сентябрь': 9,
        'октября': 10,
        'октябрь': 10,
        'ноября': 11,
        'ноябрь': 11,
        'декабря': 12,
        'декабрь': 12,
    }

    match = re.search(
        r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
        value,
        re.IGNORECASE
    )

    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        try:
            return date(year, month, day)
        except ValueError:
            return None

    match = re.search(
        r'(\d{1,2})\s+([а-яё]+)\s+(\d{4})',
        value,
        re.IGNORECASE
    )

    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        month = month_map.get(month_name)

        if not month:
            return None

        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None



def parse_upd_seller_vendor(text):
    if not text:
        return None

    normalized_text = normalize_ocr_text(
        text
    )

    lines = [
        line.strip()
        for line in normalized_text.splitlines()
        if line.strip()
    ]

    for line in lines:
        if not re.search(r'\bПродавец\b', line, re.IGNORECASE):
            continue

        match = re.search(
            r'\bПродавец\b\s*[:\-]?\s*(.+)$',
            line,
            re.IGNORECASE
        )

        if not match:
            continue

        candidate = match.group(1).strip()

        candidate = re.split(
            r'\s+(?:\(\d+\)|Покупатель\s*:|Адрес\s*:|ИНН|КПП)\b',
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE
        )[0].strip()

        vendor = extract_vendor_name_from_candidate(
            candidate
        )

        if vendor:
            return vendor

        vendor = clean_vendor(
            candidate
        )

        if vendor:
            return vendor

    patterns = [
        r'Продавец\s*:\s*(.+?)(?:\s+\(\d+\)|\s+Покупатель\s*:|\s+Адрес\s*:|\s+ИНН|\s+КПП|$)',
        r'Наименование\s+экономического\s+субъекта.*?((?:ООО|ОАО|АО|ПАО)\s+"?[^"\n;,]+\"?)',
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized_text,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            continue

        candidate = match.group(1).strip()

        vendor = extract_vendor_name_from_candidate(
            candidate
        )

        if vendor:
            return vendor

        vendor = clean_vendor(
            candidate
        )

        if vendor:
            return vendor

    return None


def parse_upd_seller_requisites(text):
    if not text:
        return None, None

    normalized_text = normalize_ocr_text(
        text
    )

    patterns = [
        r'ИНН\s*/\s*КПП\s+продавца\s*:\s*(\d{10,12})\s*/\s*(\d{9})',
        r'ИННКПП\s+продавца\s*:\s*(\d{10,12})\s*/\s*(\d{9})',
        r'ИННЖПП\s+продавца\s*:\s*(\d{10,12})\s*/\s*(\d{9})',
        r'ИННЖКПП\s+продавца\s*:\s*(\d{10,12})\s*/\s*(\d{9})',
        r'ИНН[^\n]{0,20}продавца\s*:\s*(\d{10,12})\s*/\s*(\d{9})',
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized_text,
            re.IGNORECASE
        )

        if match:
            return match.group(1), match.group(2)

    return None, None

def parse_invoice_data(text):

    text = normalize_ocr_text(
        text
    )

    if not text:

        return {
            'amount': None,
            'invoice_number': None,
            'invoice_date': None,
            'document_date': None,
            'document_type': 'invoice',
            'vendor': None,
            'inn': None,
            'kpp': None,
        }

    amount = None
    invoice_number = None
    invoice_date = None
    vendor = None

    # =====================================
    # Номер счета
    # =====================================

    invoice_patterns = [

        r'Товарная\s+накладная\s*№\s*([^\s]+)',
        r'ТОРГ\s*[-–—]?\s*12\s*№\s*([^\s]+)',
        r'Накладная\s*№\s*([^\s]+)',

        r'Счет\s+на\s+оплату\s*№\s*([^\s]+)',

        r'СЧЕТ\s*№\s*([^\s]+)',

        r'Счет\s*№\s*([^\s]+)',

        r'CUET\s*Ne\s*([^\s]+)',

        r'заказу\s+клиента\s+№?\s*([A-Za-zА-Яа-я0-9\-]+)',

        r'заказу\s+клиента\s+Ne\s*([A-Za-zА-Яа-я0-9\-]+)',

        r'Ne([A-Za-zА-Яа-я0-9\-]+)',

        r'№([A-Za-zА-Яа-я0-9\-]+)',

    ]

    for pattern in invoice_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            invoice_number = match.group(1)

            invoice_number = invoice_number.strip()

            break


    # =====================================
    # Дата счета
    # =====================================

    date_patterns = [

        r'от\s+(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4})',

        r'от\s+(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}г)',

        r'№\s*[^\s]+\s*от\s*(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4})',

        r'№\s*[^\s]+\s*от\s*(\d{1,2}\s+[А-Яа-яA-Za-z]+\s+\d{4}г)',

    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            invoice_date = match.group(1)

            invoice_date = invoice_date.strip()

            break


    # =====================================
    # Поставщик
    # =====================================

    vendor_patterns = [

        r'Поставщик.*?[":]\s*(.+)',

        r'Исполнитель.*?[":]\s*(.+)',

        r'ООО\s+"([^"]+)"',

        r'АО\s+"([^"]+)"',

        r'ПАО\s+"([^"]+)"',

        r'ОАО\s+"([^"]+)"',

        r'Общество\s+с\s+ограниченной\s+ответственностью\s+"([^"]+)"',

        r'Индивидуальный\s+предприниматель\s+(.+?)(?:ИНН|Адрес|тел|Тел|$)',

        r'Индивидуальный\s+\S*приниматель\s+(.+?)(?:ИНН|Адрес|тел|Тел|$)',

    ]

    for pattern in vendor_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            vendor = match.group(1)

            vendor = vendor.split('ИНН')[0]
            vendor = vendor.split('КПП')[0]
            vendor = vendor.split('Адрес')[0]
            vendor = vendor.split('тел')[0]
            vendor = vendor.split('Тел')[0]

            vendor = vendor.replace('\n', ' ')

            vendor = re.sub(
                r'\s+',
                ' ',
                vendor
            )

            vendor = re.sub(
                r'ИНН.*',
                '',
                vendor,
                flags=re.IGNORECASE
            )

            vendor = vendor.strip(' ,.-')

            if vendor:

                vendor = vendor.replace(
                    'OOO',
                    'ООО'
                )

                vendor = vendor.replace(
                    'OAO',
                    'ОАО'
                )

                vendor = vendor.replace(
                    'AO',
                    'АО'
                )

                vendor = vendor.strip()

            break


    # =====================================
    # Сумма
    # =====================================

    amount_patterns = [

        r'Всего\s+наименований.*?на\s+сумму\s+([\d\s$.,]+)',

        r'Всего\s+к\s+оплате[:\s]*([\d\s$.,]+)',

        r'Итого\s+с\s+НДС[:\s]*([\d\s$.,]+)',

        r'на\s+сумму\s+([\d\s$.,]+)',

        r'сумму\s+([\d\s$.,]+)\s*руб',

        r'Итого[:\s]*([\d\s$.,]+)',

    ]

    for pattern in amount_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            amount = match.group(1)

            amount = (
                amount
                .replace("'", "")
                .replace(" ", "")
                .replace(",", ".")
            )

            amount = re.sub(
                r'[^0-9.]',
                '',
                amount
            )

            amount_match = re.search(
                r'(\d+\.\d{2})',
                amount
            )

            if amount_match:

                amount = amount_match.group(1)

            break


    # -------------------------------------
    # Резервный поиск суммы
    # -------------------------------------

    if not amount:

        money_candidates = re.findall(
            r'\d[\d\s]{0,12}[.,]\d{2}',
            text
        )

        values = []

        for item in money_candidates:

            try:

                item = (
                    item
                    .replace(' ', '')
                    .replace(',', '.')
                )

                value = float(item)

                # защита от ИНН, р/с, БИК и прочего мусора

                if value <= 0:
                    continue

                if value > 10000000:
                    continue

                values.append(value)

            except:

                pass

        if values:

            amount = str(max(values))

        if amount:

            try:

                amount_float = float(amount)

                if amount_float > 500000:

                    amount = None

            except:

                amount = None

    invoice_number = parse_invoice_number(
        text
    )

    invoice_date = parse_invoice_date(
        text
    )

    document_type = detect_document_type(
        text
    )

    document_date = parse_document_date_value(
        invoice_date
    )

    amount = parse_amount(
        text
    )

    inn = extract_inn(
        text
    )

    kpp = extract_kpp(
        text
    )

    upd_vendor = parse_upd_seller_vendor(
        text
    )

    if upd_vendor:
        vendor = upd_vendor

    upd_inn, upd_kpp = parse_upd_seller_requisites(
        text
    )

    if upd_inn:
        inn = upd_inn

    if upd_kpp:
        kpp = upd_kpp

    return {
        'amount': amount,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'document_date': document_date,
        'document_type': document_type,
        'vendor': vendor,
        'inn': inn,
        'kpp': kpp,
    }
