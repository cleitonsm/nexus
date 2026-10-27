"""Dispositivos normativos: estrutura de leis e referencias na pergunta (SPEC-012).

Regras puras, sem dependencia externa. A extracao usa ``structural_heading``,
``is_normative`` e ``starts_legal_item`` para montar o caminho de secoes de
leis e regulamentos (D3, D4); a recuperacao usa ``parse_legal_reference`` e
``mentions_part`` para localizar o dispositivo pedido (D6).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# D3: abaixo disso o documento nao e tratado como norma.
NORMATIVE_MIN_ARTICLES = 5

ARTICLE_LEVEL = 5
_STRUCTURE_LEVELS = {
    "titulo": 1,
    "capitulo": 2,
    "secao": 3,
    "subsecao": 4,
}
_HEADING_MAX_WORDS = 12

_LETTER = r"A-Za-zÀ-ÖØ-öø-ÿ"
# Incisos vao ate algumas dezenas (o Art. 5º da Constituicao chega a LXXVIII);
# o teto de CCCXCIX evita ler "DI" ou "MDC" como inciso.
_ROMAN = re.compile(r"^C{0,3}(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
# Numero do artigo, com separador de milhar ("Art. 1.228." do Codigo Civil).
_NUMBER = r"(\d{1,3}(?:\.\d{3})+|\d+)"

# "Art. 5º Todos...", "Art. 10. O prazo...", "Art. 5º-A.", "Artigo 7 - ...".
# So no inicio da linha e com "Art" maiusculo: "art. 7" no meio do texto e
# remissao, nao titulo.
_ARTICLE_LINE = re.compile(
    rf"^(?:Art|ART)(?:igo|IGO)?\.?\s*{_NUMBER}"
    # Ordinal: "5º", "5°", "5o" e, em PDFs de lei, "2 o  Esta" (espaco antes do
    # "o", seguido de maiuscula).
    rf"(?:([º°ª])|(o)(?![{_LETTER}])|\s(o)(?=\s[A-ZÀ-ÖØ-Þ]))?"
    rf"(?:-([A-Z])(?![{_LETTER}]))?"
    r"\s*[.:\-–—]?\s*(.*)$"
)
_STRUCTURE_LINE = re.compile(
    r"^((?i:t[íi]tulo|cap[íi]tulo|subse[çc][ãa]o|se[çc][ãa]o))\s+"
    r"([IVXLCDM]+|(?i:[úu]nic[oa]))\b(.*)$"
)
_SECTION_TITLE = re.compile(rf"^Art\. {_NUMBER}(?:º)?(?:-([A-Z]))?$")
_ITEM_LINE = re.compile(
    r"^(?:[IVXLCDM]+\s*[-–—]\s|§\s*\d+|(?i:par[áa]grafo\s+[úu]nico)|[a-z]\)\s)"
)

_QUESTION_ARTICLE = re.compile(
    rf"\bart(?:igo)?s?\.?\s*{_NUMBER}(?:\s*[º°ª]|o(?![{_LETTER}]))?"
    rf"(?:-([a-z])(?![{_LETTER}]))?",
    re.IGNORECASE,
)
_QUESTION_ITEM = re.compile(r"\binciso\s+([ivxlcdm]+)\b", re.IGNORECASE)
# "art. 5º, XI": em minusculas, so com pontuacao ou "do/da" depois, para que
# "art. 5, vi que..." nao vire o inciso VI (revisao M3).
_QUESTION_TRAILING_ITEM = re.compile(
    r"^\s*,\s*(?:([IVXLC]+)\b|([ivxlc]+)(?=\s*(?:$|[,.;:?!]|\s+d[aeo]s?\b)))"
)
_QUESTION_PARAGRAPH = re.compile(r"(?:§|\bpar[aá]grafo)\s*(\d+)", re.IGNORECASE)
_QUESTION_SOLE_PARAGRAPH = re.compile(r"\bpar[aá]grafo\s+[uú]nico", re.IGNORECASE)

_ITEM_LABEL = re.compile(
    r"(?<![A-Za-z])([IVXLCDM]+)\s*[-–—]\s|§\s*(\d+)|(?i:(par[áa]grafo\s+[úu]nico))"
)


@dataclass(frozen=True, slots=True)
class StructuralHeading:
    """Titulo da estrutura normativa; ``remainder`` e o texto apos o rotulo."""

    level: int
    title: str
    remainder: str = ""


@dataclass(frozen=True, slots=True)
class LegalReference:
    """Dispositivo citado na pergunta: artigo e, opcionalmente, inciso ou paragrafo.

    ``paragraph`` e o numero do paragrafo ou ``"unico"``.
    """

    article: str
    item: str | None = None
    paragraph: str | None = None

    @property
    def targets_part(self) -> bool:
        return self.item is not None or self.paragraph is not None


def structural_heading(line: str) -> StructuralHeading | None:
    """Reconhece TITULO, CAPITULO, Secao, Subsecao (niveis 1 a 4) e Art. (5)."""
    text = " ".join(line.split())
    if not text:
        return None
    article = _ARTICLE_LINE.match(text)
    if article is not None:
        number, ordinal, letter_o, spaced_o, suffix, remainder = article.groups()
        title = f"Art. {number}{'º' if ordinal or letter_o or spaced_o else ''}"
        if suffix:
            title = f"{title}-{suffix}"
        return StructuralHeading(ARTICLE_LEVEL, title, remainder.strip())
    structure = _STRUCTURE_LINE.match(text)
    if structure is None:
        return None
    rest = structure.group(3).strip()
    if len(text.split()) > _HEADING_MAX_WORDS or (rest and rest[-1] in ".;,"):
        return None
    level = _STRUCTURE_LEVELS[_fold(structure.group(1))]
    return StructuralHeading(level, text)


def is_normative(lines: Iterable[str]) -> bool:
    """D3: pelo menos ``NORMATIVE_MIN_ARTICLES`` linhas comecam com ``Art. N``."""
    found = 0
    for line in lines:
        if _ARTICLE_LINE.match(line.strip()) is not None:
            found += 1
            if found >= NORMATIVE_MIN_ARTICLES:
                return True
    return False


def starts_legal_item(line: str) -> bool:
    """Inciso ("XI -"), paragrafo ("§ 1º", "Paragrafo unico") ou alinea ("a)")."""
    return _ITEM_LINE.match(line.strip()) is not None


def article_from_section_path(section_path: tuple[str, ...]) -> str | None:
    """Identificador do artigo mais interno do caminho ("5", "5-A")."""
    for title in reversed(section_path):
        match = _SECTION_TITLE.match(title)
        if match is not None:
            number, suffix = match.groups()
            number = number.replace(".", "")
            return f"{number}-{suffix}" if suffix else number
    return None


def parse_legal_reference(question: str) -> LegalReference | None:
    """Primeiro artigo citado na pergunta, com inciso ou paragrafo, se houver."""
    article = _QUESTION_ARTICLE.search(question)
    if article is None:
        return None
    number, suffix = article.groups()
    number = number.replace(".", "")
    identifier = f"{number}-{suffix.upper()}" if suffix else number
    return LegalReference(
        article=identifier,
        item=_item(question, article.end()),
        paragraph=_paragraph(question),
    )


def mentions_part(text: str, reference: LegalReference) -> bool:
    """O trecho contem o inciso ou o paragrafo pedido."""
    if reference.item is not None:
        pattern = rf"(?<![A-Za-z]){reference.item}\s*[-–—]\s"
        return re.search(pattern, text) is not None
    if reference.paragraph == "unico":
        return _QUESTION_SOLE_PARAGRAPH.search(text) is not None
    if reference.paragraph is not None:
        return re.search(rf"§\s*{reference.paragraph}(?!\d)", text) is not None
    return False


def describe_items(texts: Iterable[str]) -> str:
    """RN-36: "LXX a LXXVIII", o unico item, ou vazio sem marcador."""
    labels = [label for text in texts for label in _item_labels(text)]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]} a {labels[-1]}"


def _item_labels(text: str) -> list[str]:
    labels: list[str] = []
    for match in _ITEM_LABEL.finditer(text):
        roman, paragraph, sole = match.groups()
        if roman is not None and _ROMAN.match(roman):
            labels.append(roman)
        elif paragraph is not None:
            labels.append(f"§ {paragraph}º" if int(paragraph) < 10 else f"§ {paragraph}")
        elif sole is not None:
            labels.append("Parágrafo único")
    return labels


def _item(question: str, article_end: int) -> str | None:
    match = _QUESTION_ITEM.search(question)
    if match is not None:
        roman = match.group(1)
    else:
        trailing = _QUESTION_TRAILING_ITEM.match(question[article_end:])
        if trailing is None:
            return None
        roman = trailing.group(1) or trailing.group(2)
    roman = roman.upper()
    return roman if _ROMAN.match(roman) else None


def _paragraph(question: str) -> str | None:
    if _QUESTION_SOLE_PARAGRAPH.search(question) is not None:
        return "unico"
    match = _QUESTION_PARAGRAPH.search(question)
    return match.group(1) if match is not None else None


def _fold(text: str) -> str:
    table = str.maketrans("íÍçÇãÃ", "iIcCaA")
    return text.translate(table).lower()
