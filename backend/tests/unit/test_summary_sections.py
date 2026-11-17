"""SPEC-018 (T5): secoes inteiras do documento para o resumo hierarquico."""

from __future__ import annotations

import unittest

from src.domain import (
    BlockType,
    DocumentBlock,
    ExtractedDocument,
    SectionText,
    plan_summary_batches,
)
from src.infrastructure.chunking import StructuralSummarySplitter


class WordTokenCounter:
    """Uma palavra por token, sem especiais (conta facil de conferir)."""

    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split())


def block(text: str, *path: str, page: int | None = None) -> DocumentBlock:
    return DocumentBlock(type=BlockType.PARAGRAPH, text=text, section_path=path, page=page)


def splitter(maximum: int = 8_000) -> StructuralSummarySplitter:
    return StructuralSummarySplitter(token_counter=WordTokenCounter(), max_paragraph_tokens=maximum)


class SummarySectionsTestCase(unittest.TestCase):
    def test_consecutive_blocks_of_a_section_stay_together(self) -> None:
        document = ExtractedDocument(
            blocks=(
                block("Texto sem título antes.", page=1),
                block("Primeiro parágrafo da cláusula.", "Contrato", "Cláusula 1", page=2),
                block("Segundo parágrafo.", "Contrato", "Cláusula 1", page=3),
                block("Outra cláusula.", "Contrato", "Cláusula 2", page=3),
            )
        )
        sections = splitter().split(document)
        self.assertEqual(
            [(s.index, s.title, s.page_start, len(s.paragraphs)) for s in sections],
            [
                (0, "Início do documento", 1, 1),
                (1, "Contrato > Cláusula 1", 2, 2),
                (2, "Contrato > Cláusula 2", 3, 1),
            ],
        )
        self.assertEqual(sections[1].paragraph_tokens, (4, 2))

    def test_huge_paragraph_is_split_by_sentence_then_word(self) -> None:
        sentences = " ".join(f"Frase número {i} com cinco." for i in range(6))  # 6 x 5 palavras
        long_sentence = " ".join(["palavra"] * 23)
        document = ExtractedDocument(blocks=(block(sentences), block(long_sentence)))
        section = splitter(maximum=10).split(document)[0]
        self.assertTrue(all(tokens <= 10 for tokens in section.paragraph_tokens))
        self.assertEqual(sum(section.paragraph_tokens), 30 + 23)
        self.assertEqual(section.paragraphs[0], "Frase número 0 com cinco. Frase número 1 com cinco.")

    def test_output_feeds_the_batch_planner_and_rebuilds_the_text(self) -> None:
        document = ExtractedDocument(
            blocks=tuple(block(" ".join(["x"] * 3_000), f"Seção {i}") for i in range(4))
        )
        sections = splitter().split(document)
        batches = plan_summary_batches([section.as_tokens() for section in sections])
        self.assertEqual([batch.tokens for batch in batches], [6_000, 6_000])
        piece = batches[1].pieces[0]
        self.assertEqual(sections[piece.section_index].text_for(piece), " ".join(["x"] * 3_000))

    def test_section_text_validation(self) -> None:
        from src.domain import DomainValidationError

        with self.assertRaises(DomainValidationError):
            SectionText(index=0, title="t", paragraphs=("a",), paragraph_tokens=())


if __name__ == "__main__":
    unittest.main()
