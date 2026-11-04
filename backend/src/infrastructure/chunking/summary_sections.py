"""SPEC-018 (T5): secoes do documento para o resumo hierarquico.

Diferente do ``StructuralDocumentChunker`` (trechos de 128 tokens para o RAG),
aqui a secao fica inteira; so o paragrafo maior que o lote maximo e dividido,
por frases e, em ultimo caso, por palavras.
"""

from __future__ import annotations

from itertools import groupby

from src.domain import (
    SUMMARY_BATCH_MAX_TOKENS,
    ExtractedDocument,
    SectionText,
    TokenCounter,
)
from src.domain.chunking import SECTION_SEPARATOR

from .sentences import split_sentences

UNTITLED_SECTION = "Início do documento"


class StructuralSummarySplitter:
    def __init__(
        self,
        *,
        token_counter: TokenCounter,
        max_paragraph_tokens: int = SUMMARY_BATCH_MAX_TOKENS,
    ) -> None:
        if max_paragraph_tokens < 1:
            raise ValueError("max_paragraph_tokens must be positive.")
        self._counter = token_counter
        self._max = max_paragraph_tokens

    def split(self, document: ExtractedDocument) -> tuple[SectionText, ...]:
        sections: list[SectionText] = []
        for section_path, group in groupby(document.blocks, key=lambda block: block.section_path):
            blocks = list(group)
            paragraphs: list[str] = []
            for block in blocks:
                paragraphs.extend(self._fit(block.text))
            pages = [block.page for block in blocks if block.page is not None]
            sections.append(
                SectionText(
                    index=len(sections),
                    title=SECTION_SEPARATOR.join(section_path) or UNTITLED_SECTION,
                    paragraphs=tuple(paragraphs),
                    paragraph_tokens=tuple(self._counter.count(item) for item in paragraphs),
                    page_start=min(pages) if pages else None,
                )
            )
        return tuple(sections)

    def _fit(self, text: str) -> list[str]:
        if self._counter.count(text) <= self._max:
            return [text]
        pieces: list[str] = []
        current = ""
        for sentence in self._sentences(text):
            candidate = f"{current} {sentence}".strip()
            if current and self._counter.count(candidate) > self._max:
                pieces.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            pieces.append(current)
        return pieces

    def _sentences(self, text: str) -> list[str]:
        result: list[str] = []
        for sentence in split_sentences(text) or [text]:
            if self._counter.count(sentence) <= self._max:
                result.append(sentence)
            else:
                result.extend(self._words(sentence))
        return result

    def _words(self, sentence: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        for word in sentence.split():
            if current and self._counter.count(" ".join(current + [word])) > self._max:
                parts.append(" ".join(current))
                current = []
            current.append(word)
        if current:
            parts.append(" ".join(current))
        return parts
