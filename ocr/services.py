import re
import pytesseract

from PIL import Image
from PIL import ImageFilter
from PIL import ImageOps
from pdf2image import convert_from_path


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

POPPLER_PATH = (
    r"D:\Release-26.02.0-0\poppler-26.02.0\Library\bin"
)


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

    pages = convert_from_path(
        pdf_path,
        poppler_path=POPPLER_PATH,
        dpi=300
    )

    text_soft = ''

    for page in pages:

        page = preprocess_image(
            page
        )

        page_text = pytesseract.image_to_string(
            page,
            lang='rus+eng',
            config='--oem 3 --psm 4'
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

    pages = convert_from_path(
        pdf_path,
        poppler_path=POPPLER_PATH,
        dpi=600
    )

    for page in pages:

        page = preprocess_image_hard(
            page
        )

        page_text = pytesseract.image_to_string(
            page,
            lang='rus+eng',
            config='--oem 3 --psm 6'
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

    text = pytesseract.image_to_string(
        image,
        lang='rus+eng',
        config='--oem 3 --psm 6'
    )

    return normalize_ocr_text(
        text
    )


def clean_invoice_number(value):

    if not value:
        return None

    value = str(value)

    value = value.strip()

    value = value.replace(
        '№',
        ''
    )

    value = value.replace(
        'N',
        ''
    )

    value = value.strip(
        ' ,.;:'
    )

    value = re.sub(
        r'[^A-Za-zА-Яа-я0-9\-\/]',
        '',
        value
    )

    if not value:
        return None

    if len(value) > 40:
        return None

    return value


def parse_invoice_number(text):

    patterns = [

        r'Счет\s+на\s+оплату\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)',

        r'Сч[её]т\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)',

        r'СЧЕТ\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)',

        r'СЧЁТ\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)',

        r'№\s*([A-Za-zА-Яа-я0-9\-\/]+)\s+от\s+\d{1,2}',

        r'заказу\s+клиента\s*№?\s*([A-Za-zА-Яа-я0-9\-\/]+)',

        r'реализации\s+товаров\s+и\s+услуг\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

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

    money = r'(\d{1,3}(?:[\s\u00a0]\d{3})*[,.]\d{2}|\d+[,.]\d{2})'

    patterns = [

        rf'Всего\s+к\s+оплате[:\s]*{money}',

        rf'Итого\s+к\s+оплате[:\s]*{money}',

        rf'Итого\s+с\s+НДС[:\s]*{money}',

        rf'Всего[:\s]*{money}',

        rf'Итого[:\s]*{money}',

        rf'на\s+сумму\s+{money}',

        rf'сумму\s+{money}\s*руб',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            amount = normalize_amount(
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

        amount = normalize_amount(
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


def parse_invoice_data(text):

    text = normalize_ocr_text(
        text
    )

    if not text:

        return {
            'amount': None,
            'invoice_number': None,
            'invoice_date': None,
            'vendor': None,
            'inn': None,
            'kpp': None,
        }

    invoice_number = parse_invoice_number(
        text
    )

    invoice_date = parse_invoice_date(
        text
    )

    vendor = parse_vendor(
        text
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

    print('---------------')
    print('VENDOR:', vendor)
    print('NUMBER:', invoice_number)
    print('DATE:', invoice_date)
    print('AMOUNT:', amount)
    print('INN:', inn)
    print('KPP:', kpp)
    print('---------------')

    return {
        'amount': amount,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'vendor': vendor,
        'inn': inn,
        'kpp': kpp,
    }