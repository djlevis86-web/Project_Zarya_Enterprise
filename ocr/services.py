import os
import re

import pytesseract

from PIL import Image
from PIL import ImageFilter
from PIL import ImageOps
from pdf2image import convert_from_path
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


def get_poppler_kwargs():
    if not POPPLER_PATH:
        return {}

    return {
        "poppler_path": POPPLER_PATH,
    }


def convert_pdf_pages(pdf_path, dpi):
    try:
        return convert_from_path(
            pdf_path,
            dpi=dpi,
            **get_poppler_kwargs(),
        )

    except PDFInfoNotInstalledError as error:
        raise RuntimeError(
            "Poppler не установлен или не найден в PATH. "
            "Для OCR PDF нужны утилиты pdfinfo/pdftoppm. "
            "На Windows укажи POPPLER_PATH в .env. "
            "На Linux установи poppler-utils или запускай OCR-worker там, где Poppler доступен."
        ) from error


def image_to_text(image, config):
    try:
        return pytesseract.image_to_string(
            image,
            lang="rus+eng",
            config=config,
        )

    except TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR не установлен или не найден в PATH. "
            "На Windows укажи TESSERACT_CMD в .env. "
            "На Linux установи tesseract и языковые пакеты rus/eng "
            "или запускай OCR-worker там, где Tesseract доступен."
        ) from error


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

    pages = convert_pdf_pages(
        pdf_path,
        dpi=300,
    )

    text_soft = ''

    for page in pages:

        page = preprocess_image(
            page
        )

        page_text = image_to_text(
            page,
            config="--oem 3 --psm 4",
        )

        text_soft += page_text + '\n'

    variants.append(
        text_soft
    )

    if ocr_score(text_soft) < 55:

        text_hard = extract_text_from_pdf_hard(
            pdf_path
        )

        variants.append(
            text_hard
        )

    best_text = max(
        variants,
        key=ocr_score
    )

    return normalize_ocr_text(
        best_text
    )


def extract_text_from_pdf_hard(pdf_path):

    text = ''

    pages = convert_pdf_pages(
        pdf_path,
        dpi=600,
    )

    for page in pages:

        page = preprocess_image_hard(
            page
        )

        page_text = image_to_text(
            page,
            config="--oem 3 --psm 6",
        )

        text += page_text + '\n'

    return normalize_ocr_text(
        text
    )


def extract_text_from_image(image_path):

    image = Image.open(
        image_path
    )

    image = preprocess_image(
        image
    )

    text = image_to_text(
        image,
        config="--oem 3 --psm 6",
    )

    return normalize_ocr_text(
        text
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


def parse_amount(text):

    if not text:

        return None

    text = str(text)

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

    return 'invoice'


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

    return {
        'amount': amount,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'document_date': document_date,
        'document_type': document_type,
        'vendor': None,
        'inn': inn,
        'kpp': kpp,
    }
