import re

from django.db.models import Q

from .models import (
    Counterparty,
    Invoice,
)


OWN_COMPANY_INN = '3507012256'


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


def normalize_requisite_text(text):

    if not text:

        return ''

    text = str(text)

    replacements = {
        'AHH': 'ИНН',
        'UHH': 'ИНН',
        'WHH': 'ИНН',
        'ИННН': 'ИНН',
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    return text


def extract_requisite_candidates(text):

    text = normalize_requisite_text(
        text
    )

    if not text:

        return []

    candidates = []

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for line_number, line in enumerate(lines, start=1):

        combined_matches = re.finditer(
            r'ИНН\s*/\s*КПП\s*[:№]?\s*(\d{12}|\d{10})\s*/\s*(\d{9})',
            line,
            re.IGNORECASE
        )

        for match in combined_matches:

            candidates.append(
                {
                    'inn': match.group(1),
                    'kpp': match.group(2),
                    'line_number': line_number,
                    'line': line,
                    'source': 'combined_inn_kpp',
                }
            )

        inline_matches = re.finditer(
            r'ИНН\s*[:№]?\s*(\d{12}|\d{10})(?:\s*/\s*(\d{9}))?',
            line,
            re.IGNORECASE
        )

        for match in inline_matches:

            inn = match.group(1)
            kpp = match.group(2)

            if not kpp:

                tail = line[match.end():]

                kpp_match = re.search(
                    r'КПП\s*[:№]?\s*(\d{9})',
                    tail,
                    re.IGNORECASE
                )

                if kpp_match:

                    kpp = kpp_match.group(1)

            candidates.append(
                {
                    'inn': inn,
                    'kpp': kpp,
                    'line_number': line_number,
                    'line': line,
                    'source': 'inline_inn',
                }
            )

    return candidates



def only_digits(value):
    return re.sub(
        r'\D',
        '',
        str(value or '')
    )


def is_own_company_inn(inn):
    return only_digits(
        inn
    ) == OWN_COMPANY_INN


def is_valid_supplier_requisite_candidate(candidate):
    if not candidate:
        return False

    inn = only_digits(
        candidate.get(
            'inn'
        )
    )

    if len(inn) not in [
        10,
        12,
    ]:
        return False

    if is_own_company_inn(
        inn
    ):
        return False

    context = ' '.join(
        str(candidate.get(key) or '')
        for key in [
            'context',
            'line',
            'raw',
            'source',
        ]
    ).upper()

    if (
        any(marker in context for marker in ['ТЕЛ', 'ТЕЛЕФОН', 'ФАКС'])
        and 'ИНН' not in context
    ):
        return False

    return True


def counterparty_is_own_company(counterparty):
    if not counterparty:
        return False

    return is_own_company_inn(
        getattr(
            counterparty,
            'inn',
            None
        )
    )

def select_supplier_requisite_candidate(text):

    candidates = extract_requisite_candidates(
        text
    )

    safe_candidates = [
        candidate
        for candidate in candidates
        if is_valid_supplier_requisite_candidate(
            candidate
        )
    ]

    for candidate in safe_candidates:

        counterparty = find_counterparty_by_requisites(
            candidate.get(
                'inn'
            ),
            candidate.get(
                'kpp'
            )
        )

        if counterparty:

            return candidate

    if safe_candidates:

        return safe_candidates[0]

    return None


def extract_inn(text):

    candidate = select_supplier_requisite_candidate(
        text
    )

    if not candidate:

        return None

    return candidate.get(
        'inn'
    )


def extract_kpp(text):

    candidate = select_supplier_requisite_candidate(
        text
    )

    if not candidate:

        return None

    return candidate.get(
        'kpp'
    )


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

    if is_own_company_inn(
        inn
    ):

        return None

    queryset = get_official_counterparties_queryset().exclude(
        inn=OWN_COMPANY_INN
    ).filter(
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



def normalize_counterparty_word_set(value):
    normalized = normalize_for_search(
        value
    )

    legal_words = {
        'ООО',
        'ОАО',
        'АО',
        'ПАО',
        'ЗАО',
        'ИП',
        'ОБЩЕСТВО',
        'ОГРАНИЧЕННОЙ',
        'ОТВЕТСТВЕННОСТЬЮ',
        'ИНДИВИДУАЛЬНЫЙ',
        'ПРЕДПРИНИМАТЕЛЬ',
    }

    words = [
        word
        for word in normalized.split()
        if len(word) >= 2 and word not in legal_words
    ]

    return set(words)


def counterparty_names_match_by_words(vendor_name, candidate_name):
    if not vendor_name or not candidate_name:
        return False

    vendor_words = normalize_counterparty_word_set(
        vendor_name
    )

    candidate_words = normalize_counterparty_word_set(
        candidate_name
    )

    if not vendor_words or not candidate_words:
        return False

    if vendor_words == candidate_words:
        return True

    if len(vendor_words) >= 2 and vendor_words.issubset(candidate_words):
        return True

    if len(candidate_words) >= 2 and candidate_words.issubset(vendor_words):
        return True

    return False

def find_counterparty_by_name(vendor_name):

    if not vendor_name:

        return None

    normalized_vendor = normalize_for_search(
        vendor_name
    )

    candidates = get_official_counterparties_queryset().exclude(
        inn=OWN_COMPANY_INN
    )

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

    for counterparty in candidates:

        candidate_names = [
            counterparty.name,
            counterparty.full_name,
        ]

        for candidate_name in candidate_names:

            if not candidate_name:

                continue

            if counterparty_names_match_by_words(
                vendor_name,
                candidate_name,
            ):

                return counterparty

    return None


def extract_all_inns_from_ocr_text(text):

    result = []

    if not text:

        return result

    chunks = re.findall(
        r'\d[\d\s\\/\-]{8,}\d',
        str(text)
    )

    for chunk in chunks:

        inn = re.sub(
            r'\D+',
            '',
            chunk
        )

        if len(inn) not in (10, 12):

            continue

        if is_own_company_inn(
            inn
        ):

            continue

        if inn not in result:

            result.append(
                inn
            )

    return result


def find_counterparties_by_all_ocr_inns(text):

    matches = []

    for inn in extract_all_inns_from_ocr_text(
        text
    ):

        queryset = get_official_counterparties_queryset().exclude(
            inn=OWN_COMPANY_INN
        ).filter(
            inn=inn
        )

        for counterparty in queryset:

            if counterparty.id not in [
                item.id for item in matches
            ]:

                matches.append(
                    counterparty
                )

    return matches

def get_or_create_counterparty_from_invoice(invoice):

    source_text = invoice.ocr_text or ''

    inn = extract_inn(
        source_text
    )

    kpp = extract_kpp(
        source_text
    )

    if not inn:

        fallback_counterparties = find_counterparties_by_all_ocr_inns(
            source_text
        )

        if len(fallback_counterparties) == 1:

            counterparty = fallback_counterparties[0]

            invoice.counterparty_match_status = (
                Invoice.COUNTERPARTY_MATCH_FOUND
            )

            invoice.counterparty_match_comment = (
                f'Контрагент найден по единственному ИНН из OCR {counterparty.inn} '
                'без использования имени файла'
            )

            return counterparty

        if len(fallback_counterparties) > 1:

            invoice.counterparty_match_status = (
                Invoice.COUNTERPARTY_MATCH_AMBIGUOUS
            )

            invoice.counterparty_match_comment = (
                'В OCR найдено несколько возможных контрагентов по ИНН; '
                'автоматическое сопоставление не выполнено'
            )

            return None

        counterparty = find_counterparty_by_name(
            invoice.vendor
        )

        if counterparty:

            invoice.counterparty_match_status = (
                Invoice.COUNTERPARTY_MATCH_FOUND
            )

            invoice.counterparty_match_comment = (
                'Контрагент найден в справочнике 1С/ручном справочнике по названию поставщика'
            )

            return counterparty

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_NOT_FOUND
        )

        invoice.counterparty_match_comment = (
            'OCR не определил ИНН поставщика, контрагент по названию не найден'
        )

        return None

    counterparty = find_counterparty_by_requisites(
        inn,
        kpp
    )

    if counterparty:

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_FOUND
        )

        invoice.counterparty_match_comment = (
            f'Контрагент найден в справочнике 1С/ручном справочнике по ИНН {inn}'
        )

        return counterparty

    fallback_counterparties = find_counterparties_by_all_ocr_inns(
        source_text
    )

    if len(fallback_counterparties) == 1:

        counterparty = fallback_counterparties[0]

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_FOUND
        )

        invoice.counterparty_match_comment = (
            f'Контрагент найден по дополнительному ИНН из OCR {counterparty.inn} '
            'без использования имени файла'
        )

        return counterparty

    if len(fallback_counterparties) > 1:

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_AMBIGUOUS
        )

        invoice.counterparty_match_comment = (
            'В OCR найдено несколько возможных контрагентов по ИНН; '
            'автоматическое сопоставление не выполнено'
        )

        return None

    counterparty = find_counterparty_by_name(
        invoice.vendor
    )

    if counterparty:

        invoice.counterparty_match_status = (
            Invoice.COUNTERPARTY_MATCH_FOUND
        )

        invoice.counterparty_match_comment = (
            'Контрагент найден в справочнике 1С/ручном справочнике по названию поставщика после неудачного поиска по ИНН/КПП'
        )

        return counterparty

    invoice.counterparty_match_status = (
        Invoice.COUNTERPARTY_MATCH_NOT_FOUND
    )

    if kpp:

        invoice.counterparty_match_comment = (
            f'Контрагент не найден в справочнике 1С/ручном справочнике по ИНН {inn}, КПП {kpp}'
        )

    else:

        invoice.counterparty_match_comment = (
            f'Контрагент не найден в справочнике 1С/ручном справочнике по ИНН {inn}'
        )

    return None
