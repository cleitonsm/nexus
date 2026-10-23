from __future__ import annotations

import re

# Fim de frase: pontuacao final, fechamento opcional de aspas ou parenteses,
# espaco e inicio provavel de nova frase (maiuscula, digito ou abertura).
_BOUNDARY = re.compile(
    r"[.!?…]+[\"')\]»”’*_`]*(\s+)(?=[\"'(\[«“‘¿¡*_`]*[A-ZÀ-ÖØ-Þ0-9])"
)
_LAST_WORD = re.compile(r"(\S+?)\.[\"')\]»”’*_`]*$")
_ENUMERATOR = re.compile(r"^\(?(?:\d{1,3}|[A-Za-z])[.)]$")

_ABBREVIATIONS = frozenset(
    {
        "art", "arts", "cf", "dr", "dra", "ex", "inc", "n", "nº", "no",
        "p", "pp", "pág", "pag", "págs", "prof", "profa", "sr", "sra", "vs",
    }
)


def split_sentences(text: str) -> list[str]:
    """Divide um texto em frases, sem separar abreviaturas comuns."""
    sentences: list[str] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        candidate = text[start : match.start(1)]
        if _ends_with_abbreviation(candidate) or _is_enumerator(candidate):
            continue
        if candidate.strip():
            sentences.append(candidate.strip())
        start = match.end(1)
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _is_enumerator(candidate: str) -> bool:
    """Marcador de lista no inicio, como "1." ou "a)", nao encerra frase."""
    return _ENUMERATOR.match(candidate.strip()) is not None


def _ends_with_abbreviation(candidate: str) -> bool:
    match = _LAST_WORD.search(candidate)
    if match is None:
        return False
    word = match.group(1).lstrip("\"'([«“‘*_`").lower()
    if word in _ABBREVIATIONS:
        return True
    return len(word) == 1 and word.isalpha()
