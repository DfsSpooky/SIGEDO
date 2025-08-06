# core/templatetags/template_extras.py
from django import template
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

@register.filter
def rem_page(query_string):
    """
    Removes the 'page' parameter from a query string so that pagination
    links don't carry over the old page number.
    """
    from urllib.parse import urlencode, parse_qs

    # Parse the query string into a dictionary
    params = parse_qs(query_string)

    # Remove the 'page' key if it exists
    if 'page' in params:
        params.pop('page')

    # Re-encode the parameters back into a query string
    return urlencode(params, doseq=True)