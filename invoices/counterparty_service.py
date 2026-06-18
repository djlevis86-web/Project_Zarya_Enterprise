import re

from django.db.models import Q

from .models import (
    Counterparty,
    Invoice,
)


BAD_COUNTERPARTY_WORDS = [
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


def normalize_counterparty_name(name):

    if not name:

        return None

    name = str(name)

    replacements = {
        'OOO': 'ООО',
        'OОO': 'ООО',
        'ОOО': 'ООО',
        'OAO': 'ОАО',
        'AO ': 'АО ',
        'AHH': 'ИНН',
        'UHH': 'ИНН',
        'Г ОСКОМПЛЕКТ': 'ГОСКОМПЛЕКТ',
        'CEBEP-BET': 'СЕВЕР-ВЕТ',
        'TK APBET': 'ТК АРВЕТ',
        'TK АРВЕТ': 'ТК АРВЕТ',
        'Поётавщик': 'Поставщик',
        'Поставжик': 'Поставщик',
        'Индинидуапьный': 'Индивидуальный',
        'Индинидуальный': 'Индивидуальный',
        'Индивидуапьный': 'Индивидуальный',
        'Общество с ограниченной ответственностью': 'ООО',
        'общество с ограниченной ответственностью': 'ООО',
        '"': '',
        '«': '',
        '»': '',
        '“': '',
        '”': '',
    }

    for old, new in replacements.items():

        name = name.replace(
            old,
            new
        )

    name = re.sub(
        r'\b([А-Я])\s+([А-Я]{4,})',
        r'\1\2',
        name
    )

    name = re.split(
        r'\bИНН\b|\bКПП\b|,',
        name,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    name = re.sub(
        r'\s+',
        ' ',
        name
    )

    name = name.strip(
        ' ,.-—–'
    )

    if not name:

        return None

    upper_name = name.upper()

    for bad_word in BAD_COUNTERPARTY_WORDS:

        if bad_word in upper_name:

            return None

    if upper_name in [
        'ЗАРЯ',
        'ОАО ЗАРЯ',
    ]:

        return None

    if re.search(
        r'(СБЕРБАНК|БАНК|ПОЛУЧАТЕ)',
        upper_name
    ):

        return None

    if re.search(
        r'^(ООО|АО|ОАО|ПАО)\s+[A-ZА-ЯЁa-zа-яё]$',
        name,
        re.IGNORECASE
    ):

        return None

    digits = re.findall(
        r'\d',
        name
    )

    if len(digits) >= 9:

        return None

    if len(name) < 3:

        return None

    return name


def normalize_for_search(value):

    if not value:

        return ''

    value = str(value).upper()

    replacements = {
        'OOO': 'ООО',
        'OОO': 'ООО',
        'ОOО': 'ООО',
        'OAO': 'ОАО',
        'CEBEP-BET': 'СЕВЕР-ВЕТ',
        'TK APBET': 'ТК АРВЕТ',
        'TK АРВЕТ': 'ТК АРВЕТ',
        '"': '',
        '«': '',
        '»': '',
        '.': '',
        ',': '',
        '-': '',
        '—': '',
        '–': '',
    }

    for old, new in replacements.items():

        value = value.replace(
            old,
            new
        )

    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    return value.strip()


def extract_inn(text):

    if not text:

        return None

    text = str(text)

    text = text.replace(
        'AHH',
        'ИНН'
    )

    text = text.replace(
        'UHH',
        'ИНН'
    )

    match = re.search(
        r'ИНН\s*[:№]?\s*(\d{10,12})',
        text,
        re.IGNORECASE
    )

    if match:

        return match.group(1)

    return None


def extract_kpp(text):

    if not text:

        return None

    text = str(text)

    match = re.search(
        r'КПП\s*[:№]?\s*(\d{9})',
        text,
        re.IGNORECASE
    )

    if match:

        return match.group(1)

    return None


def extract_requisites_near_vendor(text, vendor_name):

    if not text or not vendor_name:

        return None, None

    lines = [
        line.strip()
        for line in str(text).splitlines()
        if line.strip()
    ]

    normalized_vendor = normalize_for_search(
        vendor_name
    )

    vendor_words = [
        word
        for word in normalized_vendor.split()
        if len(word) >= 4
    ]

    best_blocks = []

    for index, line in enumerate(lines):

        normalized_line = normalize_for_search(
            line
        )

        matched_words = 0

        for word in vendor_words:

            if word in normalized_line:

                matched_words += 1

        if matched_words:

            block = ' '.join(
                lines[
                    max(0, index - 1): index + 2
                ]
            )

            best_blocks.append(
                block
            )

    for block in best_blocks:

        inn = extract_inn(
            block
        )

        kpp = extract_kpp(
            block
        )

        if inn or kpp:

            return inn, kpp

    return None, None


def get_official_counterparties_queryset():

    return Counterparty.objects.filter(
        is_active=True
    ).filter(
        Q(source=Counterparty.SOURCE_1C)
        |
        Q(source=Counterparty.SOURCE_MANUAL)
    )


def find_counterparty_by_requisites(inn, kpp=None):

    if not inn:

        return None

    queryset = get_official_counterparties_queryset().filter(
        inn=inn
    )

    if kpp:

        exact = queryset.filter(
            kpp=kpp
        ).first()

        if exact:

            return exact

    count = queryset.count()

    if count == 1:

        return queryset.first()

    return None


def find_counterparty_by_name(vendor_name):

    if not vendor_name:

        return None

    normalized_vendor = normalize_for_search(
        vendor_name
    )

    candidates = get_official_counterparties_queryset()

    for counterparty in candidates:

        candidate_names = [
            counterparty.name,
            counterparty.full_name,
        ]

        for candidate_name in candidate_names:

            if not candidate_name:

                continue

            normalized_candidate = normalize_for_search(
                candidate_name
            )

            if normalized_vendor == normalized_candidate:

                return counterparty

    for counterparty in candidates:

        candidate_names = [
            counterparty.name,
            counterparty.full_name,
        ]

        for candidate_name in candidate_names:

            if not candidate_name:

                continue

            normalized_candidate = normalize_for_search(
                candidate_name
            )

            if (
                len(normalized_vendor) >= 8
                and normalized_vendor in normalized_candidate
            ):

                return counterparty

            if (
                len(normalized_candidate) >= 8
                and normalized_candidate in normalized_vendor
            ):

                return counterparty

    return None


def get_or_create_counterparty_from_invoice(invoice):

    vendor_name = normalize_counterparty_name(
        invoice.vendor
    )

    if not vendor_name:

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_NOT_FOUND
        )

        invoice.counterparty_match_comment = (
            'OCR не определил корректного поставщика'
        )

        return None

    source_text = invoice.ocr_text or ''

    inn, kpp = extract_requisites_near_vendor(
        source_text,
        vendor_name
    )

    counterparty = find_counterparty_by_requisites(
        inn,
        kpp
    )

    if not counterparty:

        counterparty = find_counterparty_by_name(
            vendor_name
        )

    if counterparty:

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_FOUND
        )

        invoice.counterparty_match_comment = (
            'Контрагент найден в справочнике 1С/ручном справочнике'
        )

        return counterparty

    invoice.counterparty_match_status = (
        Invoice.COUNTERPARTY_MATCH_NOT_FOUND
    )

    invoice.counterparty_match_comment = (
        f'Контрагент не найден в справочнике 1С: {vendor_name}'
    )

    return None