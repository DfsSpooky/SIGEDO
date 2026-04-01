import re
import unicodedata

# Mapeo explícito de variantes frecuentes del Excel hacia una identidad canónica.
# Las llaves/valores son claves ya normalizadas (sin tildes, signos ni espacios).
DOCENTE_ALIAS_KEY_MAP = {
    "albertocabrebrac": "albertocabreracaso",
    "carolinaninahuaman": "carolinaninahuancamartinez",
    "eduardopachecopena": "eduardomarinopachecopena",
    "elenacampos": "elenacamposbarbie",
    "jacintoalejoslopez": "jacintoalejandroalejoslopez",
    "juancarbajal": "juancarbajalmayhua",
    "luislobardipalomino": "luislombardipalomino",
    "luismartel": "luismartelreyes",
    "marcelinoerasmohuamanpanes": "marcelinoerasmohuamanpanez",
    "miguelventura": "miguelventurajanampa",
    "pelayoalvarezllanos": "pelayoteodoroalvarezllanos",
    "percyzavala": "percyzavalarosales",
    "romulacastilloarellano": "romulocastilloarellano",
    "samyuriporrascosme": "sanyoreiporrascosme",
    "titoriveraespinoza": "titoarmandoriveraespinoza",
    "uespinoza": "ulisesespinozaapolinario",
    "williamsantos": "williamsantoshinostroza",
}

TITLE_PREFIXES = ("dr", "dra", "mg", "lic", "ing", "prof")


def normalize_docente_key(raw_name):
    text = str(raw_name or "").strip().lower()
    if not text:
        return ""

    # Quitar títulos al inicio (Dr., Dra., Mg., etc.).
    compact = " ".join(text.split())
    for prefix in TITLE_PREFIXES:
        if compact.startswith(prefix + " "):
            compact = compact[len(prefix) + 1 :]
            break

    normalized = "".join(
        c
        for c in unicodedata.normalize("NFD", compact)
        if unicodedata.category(c) != "Mn"
    )
    normalized = re.sub(r"[^a-zA-Z0-9]", "", normalized)

    # Correcciones históricas de tipeo detectadas en los excels.
    normalized = normalized.replace("ananavarroporras", "anamarianavarroporras")
    normalized = normalized.replace("betyricaldi", "bettyricaldi")
    normalized = normalized.replace("evacondorsurichaqui", "evaelsacondorsurichaqui")

    return DOCENTE_ALIAS_KEY_MAP.get(normalized, normalized)
