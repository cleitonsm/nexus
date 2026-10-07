import unittest

from src.domain import BlockType, DocumentBlock, ExtractedDocument
from src.infrastructure.chunking import (
    StructuralDocumentChunker,
    split_sentences,
)


class WordTokenCounter:
    """Duble deterministico: uma palavra por token, mais dois especiais."""

    def __init__(self, max_tokens: int = 128) -> None:
        self._max_tokens = max_tokens

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    def count(self, text: str) -> int:
        return len(text.split()) + 2


def _chunker(
    max_tokens: int = 20,
    overlap_sentences: int = 1,
    max_prefix_tokens: int = 8,
    model_limit: int = 128,
) -> StructuralDocumentChunker:
    return StructuralDocumentChunker(
        token_counter=WordTokenCounter(model_limit),
        max_tokens=max_tokens,
        overlap_sentences=overlap_sentences,
        max_prefix_tokens=max_prefix_tokens,
    )


def _paragraph(text: str, section: tuple[str, ...] = (), page: int | None = None):
    return DocumentBlock(
        type=BlockType.PARAGRAPH,
        text=text,
        section_path=section,
        page=page,
    )


def _document(*blocks: DocumentBlock) -> ExtractedDocument:
    return ExtractedDocument(blocks=tuple(blocks))


def _sentence(label: str, words: int = 5) -> str:
    return " ".join([label] + ["palavra"] * (words - 2) + ["fim."])


class SentenceSplitTestCase(unittest.TestCase):
    def test_splits_on_terminal_punctuation(self) -> None:
        self.assertEqual(
            split_sentences("Primeira frase. Segunda frase? Terceira!"),
            ["Primeira frase.", "Segunda frase?", "Terceira!"],
        )

    def test_does_not_split_on_abbreviation(self) -> None:
        self.assertEqual(
            split_sentences("Conforme o art. 5 da norma. Segue o texto."),
            ["Conforme o art. 5 da norma.", "Segue o texto."],
        )

    def test_does_not_split_before_lowercase(self) -> None:
        self.assertEqual(
            split_sentences("Versao 1.2 e posterior. Fim."),
            ["Versao 1.2 e posterior.", "Fim."],
        )

    def test_keeps_closing_quote_with_sentence(self) -> None:
        self.assertEqual(
            split_sentences('Ele disse "pare." Depois saiu.'),
            ['Ele disse "pare."', "Depois saiu."],
        )

    def test_list_enumerator_is_not_a_sentence(self) -> None:
        self.assertEqual(
            split_sentences("1. Abra o menu. Depois salve."),
            ["1. Abra o menu.", "Depois salve."],
        )

    def test_splits_after_markdown_emphasis(self) -> None:
        self.assertEqual(
            split_sentences("**Nota.** O prazo e fixo."),
            ["**Nota.**", "O prazo e fixo."],
        )

    def test_text_without_terminal_punctuation_is_one_sentence(self) -> None:
        self.assertEqual(split_sentences("  sem ponto final  "), ["sem ponto final"])

    def test_empty_text_has_no_sentences(self) -> None:
        self.assertEqual(split_sentences("   "), [])


class ConfigurationTestCase(unittest.TestCase):
    def test_rejects_limit_above_model_capacity(self) -> None:
        with self.assertRaises(ValueError):
            _chunker(max_tokens=129, model_limit=128)

    def test_accepts_limit_equal_to_model_capacity(self) -> None:
        _chunker(max_tokens=128, model_limit=128)

    def test_rejects_negative_overlap(self) -> None:
        with self.assertRaises(ValueError):
            _chunker(overlap_sentences=-1)

    def test_rejects_prefix_budget_that_leaves_no_room(self) -> None:
        with self.assertRaises(ValueError):
            _chunker(max_tokens=20, max_prefix_tokens=20)


class TokenLimitTestCase(unittest.TestCase):
    """CT-07: nenhum chunk excede o limite de tokens configurado."""

    def test_no_chunk_exceeds_limit(self) -> None:
        counter = WordTokenCounter()
        long_paragraph = " ".join(_sentence(f"S{i}", 6) for i in range(30))
        table = "\n".join(
            ["| col a | col b |", "|---|---|"]
            + [f"| valor {i} | outro {i} |" for i in range(20)]
        )
        document = _document(
            _paragraph(long_paragraph, ("Manual", "Secao longa")),
            DocumentBlock(
                type=BlockType.TABLE,
                text=table,
                section_path=("Manual", "Tabela"),
                header_lines=2,
            ),
            DocumentBlock(
                type=BlockType.CODE,
                text="\n".join(f"linha de codigo numero {i}" for i in range(15)),
                section_path=("Manual", "Codigo"),
            ),
        )
        chunks = _chunker(max_tokens=20).chunk(document)
        self.assertGreater(len(chunks), 5)
        for chunk in chunks:
            self.assertLessEqual(counter.count(chunk.text), 20, chunk.text)

    def test_sentence_longer_than_limit_is_split_within_limit(self) -> None:
        counter = WordTokenCounter()
        giant = " ".join(["termo"] * 60) + "."
        chunks = _chunker(max_tokens=20).chunk(_document(_paragraph(giant)))
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(counter.count(chunk.text), 20)
        self.assertEqual(
            sum(chunk.text.count("termo") for chunk in chunks),
            60,
        )


class StructureTestCase(unittest.TestCase):
    """CT-06: nao corta frases nem separa cabecalho e linhas de tabela."""

    def test_chunks_end_at_sentence_boundaries(self) -> None:
        paragraph = " ".join(_sentence(f"S{i}", 6) for i in range(12))
        chunks = _chunker(max_tokens=20).chunk(_document(_paragraph(paragraph)))
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(chunk.text.endswith("fim."), chunk.text)

    def test_paragraph_that_fits_is_not_split(self) -> None:
        first = _sentence("A1", 6) + " " + _sentence("A2", 6)
        second = _sentence("B1", 5) + " " + _sentence("B2", 5)
        chunks = _chunker(max_tokens=20, overlap_sentences=0).chunk(
            _document(_paragraph(first), _paragraph(second))
        )
        self.assertEqual([chunk.text for chunk in chunks], [first, second])

    def test_small_blocks_share_a_chunk(self) -> None:
        chunks = _chunker(max_tokens=20).chunk(
            _document(_paragraph("Um texto curto."), _paragraph("Outro texto."))
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Um texto curto.\n\nOutro texto.")

    def test_list_items_are_joined_by_single_newline(self) -> None:
        items = [
            DocumentBlock(type=BlockType.LIST_ITEM, text=f"- item {i}")
            for i in range(3)
        ]
        chunks = _chunker(max_tokens=20).chunk(_document(*items))
        self.assertEqual(chunks[0].text, "- item 0\n- item 1\n- item 2")

    def test_table_rows_stay_with_header(self) -> None:
        header = "| contrato | recesso |\n|---|---|"
        rows = [f"| contrato {i} meses | {i} dias |" for i in range(1, 13)]
        table = DocumentBlock(
            type=BlockType.TABLE,
            text=header + "\n" + "\n".join(rows),
            section_path=("Ferias",),
            header_lines=2,
        )
        chunks = _chunker(max_tokens=24).chunk(_document(table))
        self.assertGreater(len(chunks), 1)
        seen_rows: list[str] = []
        for chunk in chunks:
            self.assertTrue(chunk.text.startswith("Ferias\n\n" + header), chunk.text)
            seen_rows.extend(
                line for line in chunk.text.split("\n") if line in rows
            )
        self.assertEqual(seen_rows, rows)

    def test_table_that_fits_is_kept_whole(self) -> None:
        text = "| a | b |\n|---|---|\n| 1 | 2 |"
        table = DocumentBlock(type=BlockType.TABLE, text=text, header_lines=2)
        chunks = _chunker(max_tokens=30).chunk(_document(table))
        self.assertEqual([chunk.text for chunk in chunks], [text])

    def test_no_content_is_lost(self) -> None:
        sentences = [_sentence(f"S{i}", 6) for i in range(25)]
        chunks = _chunker(max_tokens=20).chunk(
            _document(_paragraph(" ".join(sentences), ("Secao",)))
        )
        joined = "\n".join(chunk.text for chunk in chunks)
        for sentence in sentences:
            self.assertIn(sentence, joined)


class OverlapTestCase(unittest.TestCase):
    def _sentences(self) -> list[str]:
        return [_sentence(f"S{i}", 6) for i in range(9)]

    def test_next_chunk_repeats_last_sentence_of_previous(self) -> None:
        chunks = _chunker(max_tokens=20, overlap_sentences=1).chunk(
            _document(_paragraph(" ".join(self._sentences())))
        )
        self.assertGreater(len(chunks), 2)
        for previous, current in zip(chunks, chunks[1:]):
            last = split_sentences(previous.text)[-1]
            self.assertTrue(current.text.startswith(last), current.text)

    def test_overlap_can_be_disabled(self) -> None:
        sentences = self._sentences()
        chunks = _chunker(max_tokens=20, overlap_sentences=0).chunk(
            _document(_paragraph(" ".join(sentences)))
        )
        joined = " ".join(chunk.text for chunk in chunks)
        self.assertEqual(joined, " ".join(sentences))

    def test_overlap_does_not_cross_sections(self) -> None:
        chunks = _chunker(max_tokens=20).chunk(
            _document(
                _paragraph(_sentence("A", 6), ("Um",)),
                _paragraph(_sentence("B", 6), ("Dois",)),
            )
        )
        self.assertEqual(len(chunks), 2)
        self.assertNotIn("A palavra", chunks[1].text)


class MetadataTestCase(unittest.TestCase):
    """CT-08 (parte do chunker): secao e pagina em cada chunk."""

    def test_chunk_carries_section_page_and_prefix(self) -> None:
        chunks = _chunker(max_tokens=30).chunk(
            _document(
                _paragraph(
                    "Recesso de trinta dias.",
                    ("Politica de Ferias", "Estagiarios"),
                    page=4,
                )
            )
        )
        chunk = chunks[0]
        self.assertEqual(chunk.section_path, ("Politica de Ferias", "Estagiarios"))
        self.assertEqual(chunk.section_label, "Politica de Ferias > Estagiarios")
        self.assertEqual(chunk.page, 4)
        self.assertEqual(
            chunk.text,
            "Politica de Ferias > Estagiarios\n\nRecesso de trinta dias.",
        )

    def test_block_without_section_has_no_prefix(self) -> None:
        chunks = _chunker().chunk(_document(_paragraph("Texto solto.")))
        self.assertEqual(chunks[0].text, "Texto solto.")
        self.assertEqual(chunks[0].section_path, ())

    def test_new_section_starts_new_chunk(self) -> None:
        chunks = _chunker(max_tokens=40).chunk(
            _document(
                _paragraph("Texto um.", ("A",)),
                _paragraph("Texto dois.", ("B",)),
            )
        )
        self.assertEqual(
            [chunk.section_path for chunk in chunks],
            [("A",), ("B",)],
        )

    def test_indexes_are_sequential(self) -> None:
        paragraph = " ".join(_sentence(f"S{i}", 6) for i in range(12))
        chunks = _chunker(max_tokens=20).chunk(
            _document(_paragraph(paragraph, ("A",)), _paragraph(paragraph, ("B",)))
        )
        self.assertEqual(
            [chunk.index for chunk in chunks],
            list(range(len(chunks))),
        )

    def test_chunk_page_is_the_page_of_its_first_block(self) -> None:
        chunks = _chunker(max_tokens=40).chunk(
            _document(
                _paragraph("Texto da pagina dois.", ("A",), page=2),
                _paragraph("Texto da pagina tres.", ("A",), page=3),
            )
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page, 2)

    def test_long_section_path_keeps_innermost_titles_in_prefix(self) -> None:
        path = (
            "Manual geral de operacao do sistema corporativo",
            "Capitulo de politicas internas de pessoal",
            "Ferias",
        )
        chunks = _chunker(max_tokens=20, max_prefix_tokens=5).chunk(
            _document(_paragraph("Recesso de trinta dias.", path))
        )
        self.assertEqual(chunks[0].text, "Ferias\n\nRecesso de trinta dias.")
        self.assertEqual(chunks[0].section_path, path)

    def test_prefix_is_dropped_when_no_title_fits(self) -> None:
        path = ("Titulo demasiado longo para caber no orcamento do prefixo",)
        chunks = _chunker(max_tokens=20, max_prefix_tokens=4).chunk(
            _document(_paragraph("Corpo curto.", path))
        )
        self.assertEqual(chunks[0].text, "Corpo curto.")
        self.assertEqual(chunks[0].section_path, path)


if __name__ == "__main__":
    unittest.main()
