from __future__ import annotations

import re
import unicodedata
from collections import Counter
from hashlib import blake2b

from src.domain import SparseEncodingParameters, SparseVector

# Compostos como "NR-35", "ISO/IEC-27001" ou "v1.11.3" valem tambem como um
# termo unico: e a correspondencia exata que a busca densa nao garante.
_WORD = re.compile(r"[a-z0-9]+")
_COMPOUND = re.compile(r"[a-z0-9]+(?:[-./][a-z0-9]+)+")

# SPEC-012 (D5): "Art. 5º" e "artigo 5" precisam gerar os mesmos termos. O
# ordinal sai antes do NFKD, que transformaria "º" em "o"; "5o" digitado na
# pergunta vira "5" depois. Mudar estas regras exige reindexar (PIPELINE_VERSION).
_ORDINAL_MARK = re.compile(r"(\d)\s*[º°ª]")
_TYPED_ORDINAL = re.compile(r"^(\d+)[oa]$")
_SECTION_SIGN = re.compile(r"§")
_LEGAL_SYNONYMS = {
    "artigo": "art",
    "artigos": "art",
    "arts": "art",
    "paragrafo": "par",
    "paragrafos": "par",
}

_STOPWORDS = frozenset(
    """
    a ao aos as à às com como da das de do dos e é em entre essa esse esta
    este eu foi há isso isto já la lhe mais mas me na nas não nem no nos o os
    ou para pela pelas pelo pelos por qual quais quando que quem se sem ser
    seu seus são sua suas também te tem um uma umas uns
    """.split()
)

DEFAULT_BM25_K1 = 1.2
DEFAULT_BM25_B = 0.75
# Comprimento medio de referencia, em termos. Os chunks tem tamanho quase
# uniforme (limite do modelo de embedding), entao a normalizacao pesa pouco.
DEFAULT_BM25_AVERAGE_LENGTH = 64.0


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_FOLDED_STOPWORDS = frozenset(_fold(word) for word in _STOPWORDS)


def tokenize(text: str) -> list[str]:
    """Termos em minusculas e sem acento, mais os compostos inteiros.

    Referencias normativas sao normalizadas (D5 da SPEC-012): ordinais perdem
    o marcador, ``artigo`` vira ``art`` e ``§``/``paragrafo`` viram ``par``.
    """
    marked = _SECTION_SIGN.sub(" par ", _ORDINAL_MARK.sub(r"\1", text))
    folded = _fold(marked)
    words = [
        _normalize_word(word)
        for word in _WORD.findall(folded)
        if word not in _FOLDED_STOPWORDS
    ]
    return words + _COMPOUND.findall(folded)


def _normalize_word(word: str) -> str:
    ordinal = _TYPED_ORDINAL.match(word)
    if ordinal is not None:
        return ordinal.group(1)
    return _LEGAL_SYNONYMS.get(word, word)


def _term_index(term: str) -> int:
    """Posicao estavel do termo (32 bits), igual em qualquer processo."""
    return int.from_bytes(blake2b(term.encode("utf-8"), digest_size=4).digest(), "big")


class Bm25SparseEmbeddingGateway:
    """Vetores esparsos BM25 calculados localmente (RNF-26, ADR 0007).

    O documento leva o componente de frequencia do BM25; a consulta leva peso
    1 por termo; o IDF e aplicado pelo Qdrant (modificador ``idf``).
    """

    def __init__(
        self,
        *,
        k1: float = DEFAULT_BM25_K1,
        b: float = DEFAULT_BM25_B,
        average_length: float = DEFAULT_BM25_AVERAGE_LENGTH,
    ) -> None:
        if k1 < 0 or not 0.0 <= b <= 1.0 or average_length <= 0:
            raise ValueError("invalid BM25 parameters.")
        self._k1 = k1
        self._b = b
        self._average_length = average_length

    @property
    def parameters(self) -> SparseEncodingParameters:
        """Parametros vigentes, registrados com cada collection (PC-D2)."""
        return SparseEncodingParameters(
            k1=self._k1, b=self._b, average_length=self._average_length
        )

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._embed_document(text) for text in texts]

    def embed_query(self, text: str) -> SparseVector:
        return _to_vector({term: 1.0 for term in tokenize(text)})

    def _embed_document(self, text: str) -> SparseVector:
        terms = tokenize(text)
        length_norm = 1 - self._b + self._b * len(terms) / self._average_length
        return _to_vector(
            {
                term: frequency * (self._k1 + 1) / (frequency + self._k1 * length_norm)
                for term, frequency in Counter(terms).items()
            }
        )


def _to_vector(weights: dict[str, float]) -> SparseVector:
    by_index: dict[int, float] = {}
    for term, weight in weights.items():
        index = _term_index(term)
        # Colisao de hash: os pesos se somam, mantendo os indices unicos.
        by_index[index] = by_index.get(index, 0.0) + weight
    ordered = sorted(by_index.items())
    return SparseVector(
        indices=tuple(index for index, _ in ordered),
        values=tuple(value for _, value in ordered),
    )
