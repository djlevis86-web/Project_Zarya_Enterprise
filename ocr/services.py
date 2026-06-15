import re
import pytesseract

from PIL import Image
from pdf2image import convert_from_path
from PIL import ImageFilter
from PIL import ImageOps

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

POPPLER_PATH = (
    r"D:\Release-26.02.0-0\poppler-26.02.0\Library\bin"
)

def preprocess_image(image):

    image = image.convert("L")

    image = ImageOps.autocontrast(image)

    image = image.filter(
        ImageFilter.MedianFilter(size=3)
    )

    image = image.point(
        lambda x: 0 if x < 170 else 255,
        mode='1'
    )

    image = image.convert("L")

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image

def extract_text_from_pdf(pdf_path):

    text = ""

    pages = convert_from_path(
        pdf_path,
        poppler_path=POPPLER_PATH,
        dpi=300
    )

    for page in pages:

        page = preprocess_image(page)

        page_text = pytesseract.image_to_string(
            page,
            lang='rus+eng',
            config='--oem 3 --psm 4'
        )

        text += page_text + "\n"

    need_hard_ocr = (
        len(text) < 1500
        or "$" in text
        or "N2-" in text
        or "6С-" in text
    )

    if need_hard_ocr:

        hard_text = extract_text_from_pdf_hard(
            pdf_path
        )

        if len(hard_text) > len(text):
            text = hard_text

    text = text.replace('№', 'N')
    text = text.replace('Ne', '№')
    text = text.replace('No', '№')
    text = text.replace('|', 'I')
    
    text = re.sub(
        r'(\d)\$(\d)',
        r'\g<1>3\g<2>',
        text
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

    return text

def extract_text_from_pdf_hard(pdf_path):

    text = ""

    pages = convert_from_path(
        pdf_path,
        poppler_path=POPPLER_PATH,
        dpi=600
    )

    for page in pages:

        page = page.convert("L")

        page = ImageOps.autocontrast(page)

        page = page.filter(
            ImageFilter.MedianFilter(size=5)
        )

        page = page.point(
            lambda x: 255 if x > 150 else 0,
            mode='1'
        )

        page = page.convert("L")

        page_text = pytesseract.image_to_string(
            page,
            lang='rus+eng',
            config='--oem 3 --psm 6'
        )

        text += page_text + "\n"

    return text

def extract_text_from_image(image_path):

    image = Image.open(image_path)

    image = preprocess_image(image)

    text = pytesseract.image_to_string(
        image,
        lang='rus+eng',
        config='--psm 6'
    )

    return text


def parse_invoice_data(text):

    if not text:
        return {
            'amount': None,
            'invoice_number': None,
            'invoice_date': None,
            'vendor': None,
        }
    
    text = text.replace("Ha", "на")
    text = text.replace("maa", "мая")
    text = text.replace("AHH", "ИНН")
    text = text.replace("Cu.", "Сч.")
    text = text.replace("N ", "№ ")
    text = text.replace("N°", "№")
    text = text.replace("Сч.", "Счет")

    amount = None
    invoice_number = None
    invoice_date = None
    vendor = None

    # =====================================
    # Номер счета
    # =====================================

    invoice_patterns = [
        r'Счет\s+на\s+оплату\s*№\s*(\d+)',

        r'Счет\s*№\s*(\d+)',

        r'№\s*(\d+)\s*от',
        
        r'Счет.*?№\s*([A-Za-zА-Яа-я0-9\-]+)\s*от',

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

        r'Поставщик.*?(ООО\s+"[^"]+")',

        r'Поставщик.*?(АО\s+"[^"]+")',

        r'Поставщик.*?(ПАО\s+"[^"]+")',

        r'Поставщик.*?(ОАО\s+"[^"]+")',

        r'(ООО\s+"[^"]+")',

        r'(АО\s+"[^"]+")',

        r'(ПАО\s+"[^"]+")',

        r'(ОАО\s+"[^"]+")',

    ]

    for pattern in vendor_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            vendor = match.group(1)

            vendor = vendor.replace('Г ОСКОМПЛЕКТ', 'ГОСКОМПЛЕКТ')

            vendor = vendor.replace('OOO', 'ООО')
            vendor = vendor.replace('OAO', 'ОАО')
            vendor = vendor.replace('AO', 'АО')

            vendor = re.sub(
                r'\s+',
                ' ',
                vendor
            )

            vendor = vendor.strip()

            vendor = re.sub(
                r'\b([А-Я])\s+([А-Я]{5,})',
                r'\1\2',
                vendor
            )

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

    print("---------------")
    print("VENDOR:", vendor)
    print("NUMBER:", invoice_number)
    print("DATE:", invoice_date)
    print("AMOUNT:", amount)
    print("---------------")

    return {
        'amount': amount,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'vendor': vendor,
    }