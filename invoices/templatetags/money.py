from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def money_ru(value):
    """
    Формат денег для русскоязычного интерфейса:
    10613812.00 -> 10 613 812,00 ₽
    """
    if value is None or value == "":
        return "0,00 ₽"

    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return value

    sign = "- " if amount < 0 else ""
    amount = abs(amount)

    integer_part, decimal_part = f"{amount:.2f}".split(".")

    groups = []

    while integer_part:
        groups.append(integer_part[-3:])
        integer_part = integer_part[:-3]

    formatted_integer = " ".join(reversed(groups))

    return f"{sign}{formatted_integer},{decimal_part} ₽"
