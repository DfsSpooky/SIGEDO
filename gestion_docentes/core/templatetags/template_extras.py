# core/templatetags/template_extras.py
from django import template
from ..utils.encryption import encrypt_id

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='roman')
def roman(number):
    """Convierte un número entero a un número romano."""
    if not isinstance(number, int):
        return number
    
    val = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
        ]
    syb = [
        "M", "CM", "D", "CD",
        "C", "XC", "L", "XL",
        "X", "IX", "V", "IV",
        "I"
        ]
    
    roman_num = ''
    i = 0
    while  number > 0:
        for _ in range(number // val[i]):
            roman_num += syb[i]
            number -= val[i]
        i += 1
    return roman_num

@register.filter(name='encrypt')
def encrypt(value):
    """
    Encrypts a value using the encrypt_id utility.
    """
    return encrypt_id(value)

@register.filter(name='widget_type')
def widget_type(field):
    return field.field.widget.__class__.__name__
