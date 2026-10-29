from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def group_bd(integer_text):
    """Group digits the Bangladeshi way: 1234567 -> 12,34,567."""
    if len(integer_text) <= 3:
        return integer_text
    head, tail = integer_text[:-3], integer_text[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ','.join(parts + [tail])


@register.filter
def taka(value):
    """5499.00 -> '5,499'; 3399.15 -> '3,399.15'; 1234567 -> '12,34,567'. Use as: Tk {{ price|taka }}"""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    negative = number < 0
    number = abs(number).quantize(Decimal('0.01'))
    whole, _, fraction = f"{number:.2f}".partition('.')
    text = group_bd(whole)
    if fraction != '00':
        text += '.' + fraction
    return ('-' if negative else '') + text


ICONS = [
    (('earbud', 'air bud', 'airbud', 'bud', 'headphone', 'headset', 'audio', 'speaker', 'airpod'), 'bi-headphones'),
    (('watch', 'band'), 'bi-smartwatch'),
    (('laptop', 'macbook', 'notebook', 'computer'), 'bi-laptop'),
    (('tablet', 'ipad', 'tab'), 'bi-tablet'),
    (('phone', 'mobile'), 'bi-phone'),
    (('charger', 'power', 'battery', 'cable'), 'bi-lightning-charge'),
    (('case', 'cover', 'protector', 'glass'), 'bi-shield-check'),
    (('accessor',), 'bi-plug'),
]


@register.filter
def category_icon(name):
    """Pick a Bootstrap icon from a category name."""
    lowered = str(name).lower()
    for words, icon in ICONS:
        if any(w in lowered for w in words):
            return icon
    return 'bi-grid'
