import unicodedata

from django.http import JsonResponse


def remove_accents(input_str):
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def health_check(_request):
    return JsonResponse({"status": "ok"})
