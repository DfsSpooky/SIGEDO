from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def roman(value):
    try:
        value = int(value)
    except (ValueError, TypeError):
        return value
    
    if not (0 < value < 4000):
        return str(value)
        
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
    while value > 0:
        for _ in range(value // val[i]):
            roman_num += syb[i]
            value -= val[i]
        i += 1
    return roman_num
