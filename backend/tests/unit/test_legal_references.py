"""SPEC-20261026-012: reconhecimento de dispositivos normativos (CT-91, CT-93)."""

from __future__ import annotations

import unittest

from src.domain import (
    NORMATIVE_MIN_ARTICLES,
    LegalReference,
    article_from_section_path,
    describe_items,
    is_normative,
    mentions_part,
    parse_legal_reference,
    starts_legal_item,
    structural_heading,
)


class StructuralHeadingTestCase(unittest.TestCase):
    """CT-91: titulos da estrutura normativa e seus niveis (D4)."""

    def test_article_with_ordinal_keeps_the_caput_as_remainder(self) -> None:
        heading = structural_heading("Art. 5º Todos são iguais perante a lei.")
        self.assertIsNotNone(heading)
        self.assertEqual(heading.level, 5)
        self.assertEqual(heading.title, "Art. 5º")
        self.assertEqual(heading.remainder, "Todos são iguais perante a lei.")

    def test_article_variants(self) -> None:
        cases = {
            "Art. 10. O prazo é de dez dias.": ("Art. 10", "O prazo é de dez dias."),
            "Art. 1o Fica instituído o regulamento.": (
                "Art. 1º",
                "Fica instituído o regulamento.",
            ),
            "Art. 5º-A. Os dados ficam protegidos.": (
                "Art. 5º-A",
                "Os dados ficam protegidos.",
            ),
            "Artigo 7 - Compete ao conselho deliberar.": (
                "Art. 7",
                "Compete ao conselho deliberar.",
            ),
            "Art. 3º": ("Art. 3º", ""),
        }
        for line, (title, remainder) in cases.items():
            with self.subTest(line=line):
                heading = structural_heading(line)
                self.assertIsNotNone(heading)
                self.assertEqual(heading.title, title)
                self.assertEqual(heading.remainder, remainder)

    def test_thousands_separator_is_part_of_the_number(self) -> None:
        """Revisao A1: Codigo Civil e CPC numeram "Art. 1.228."."""
        heading = structural_heading("Art. 1.228. O proprietário tem a faculdade de usar.")
        self.assertEqual(heading.title, "Art. 1.228")
        self.assertEqual(heading.remainder, "O proprietário tem a faculdade de usar.")
        self.assertEqual(structural_heading("Art. 1.000 Texto.").title, "Art. 1.000")

    def test_ordinal_separated_by_a_space(self) -> None:
        """Achado no PDF de uma lei real: "Art. 2 o  Esta Lei entra em vigor"."""
        heading = structural_heading("Art. 2 o  Esta Lei entra em vigor.")
        self.assertEqual(heading.title, "Art. 2º")
        self.assertEqual(heading.remainder, "Esta Lei entra em vigor.")
        # Minuscula depois: "o" e artigo definido, nao ordinal.
        heading = structural_heading("Art. 1 o prazo é de dez dias.")
        self.assertEqual(heading.title, "Art. 1")
        self.assertEqual(heading.remainder, "o prazo é de dez dias.")

    def test_a_letter_after_a_spaced_dash_is_not_an_article_suffix(self) -> None:
        heading = structural_heading("Art. 5º - A lei não prejudicará o direito.")
        self.assertEqual(heading.title, "Art. 5º")
        self.assertEqual(heading.remainder, "A lei não prejudicará o direito.")

    def test_structure_levels(self) -> None:
        cases = {
            "TÍTULO II": 1,
            "Título III - Das Disposições Gerais": 1,
            "CAPÍTULO I": 2,
            "Seção II": 3,
            "SUBSEÇÃO III": 4,
            "CAPÍTULO ÚNICO": 2,
        }
        for line, level in cases.items():
            with self.subTest(line=line):
                heading = structural_heading(line)
                self.assertIsNotNone(heading)
                self.assertEqual(heading.level, level)
                self.assertEqual(heading.title, line)
                self.assertEqual(heading.remainder, "")

    def test_ordinary_lines_are_not_headings(self) -> None:
        for line in (
            "art. 5º, inciso XI, da Constituição",
            "Arte e cultura no regulamento",
            "Título de eleitor é exigido no cadastro e outros documentos pessoais do candidato.",
            "O capítulo seguinte trata das férias.",
            "1 Introdução",
        ):
            with self.subTest(line=line):
                self.assertIsNone(structural_heading(line))


class NormativeDetectionTestCase(unittest.TestCase):
    """CT-91: limiar de artigos da D3."""

    def test_threshold_is_five_article_lines(self) -> None:
        self.assertEqual(NORMATIVE_MIN_ARTICLES, 5)
        lines = [f"Art. {number}º Texto do artigo." for number in range(1, 5)]
        self.assertFalse(is_normative(lines))
        self.assertTrue(is_normative(lines + ["Art. 5º Outro texto."]))

    def test_references_inside_sentences_do_not_count(self) -> None:
        lines = ["Conforme o art. 7 da CLT, o prazo é de dez dias."] * 10
        self.assertFalse(is_normative(lines))


class LegalItemTestCase(unittest.TestCase):
    def test_item_markers_start_a_new_block(self) -> None:
        for line in (
            "I - homens e mulheres são iguais;",
            "XI – a casa é asilo inviolável;",
            "§ 1º As normas têm aplicação imediata.",
            "Parágrafo único. O regulamento vale para todos.",
            "a) o requerimento do interessado;",
        ):
            with self.subTest(line=line):
                self.assertTrue(starts_legal_item(line))

    def test_continuation_lines_are_not_items(self) -> None:
        for line in ("garantindo-se aos brasileiros e aos estrangeiros", "Imposto - 3%"):
            with self.subTest(line=line):
                self.assertFalse(starts_legal_item(line))


class ArticleFromSectionPathTestCase(unittest.TestCase):
    def test_last_article_in_path_is_the_identifier(self) -> None:
        self.assertEqual(
            article_from_section_path(("TÍTULO II", "CAPÍTULO I", "Art. 5º")), "5"
        )
        self.assertEqual(article_from_section_path(("Art. 5º-A",)), "5-A")
        self.assertEqual(article_from_section_path(("Art. 12",)), "12")

    def test_thousands_separator_is_removed_from_the_identifier(self) -> None:
        self.assertEqual(article_from_section_path(("Art. 1.228",)), "1228")
        self.assertEqual(article_from_section_path(("Art. 2.046-A",)), "2046-A")

    def test_path_without_article(self) -> None:
        self.assertIsNone(article_from_section_path(("TÍTULO I",)))
        self.assertIsNone(article_from_section_path(()))
        self.assertIsNone(article_from_section_path(("Arte",)))


class ParseLegalReferenceTestCase(unittest.TestCase):
    """CT-93: referencia a dispositivo na pergunta."""

    def test_article_spellings(self) -> None:
        for question in (
            "Explique o artigo 5 da constituição",
            "o que diz o art. 5º?",
            "Art 5o do regulamento",
            "ARTIGO 5",
        ):
            with self.subTest(question=question):
                self.assertEqual(
                    parse_legal_reference(question), LegalReference(article="5")
                )

    def test_article_with_letter_suffix(self) -> None:
        self.assertEqual(
            parse_legal_reference("explique o art. 5º-A"), LegalReference(article="5-A")
        )

    def test_item_in_roman_numerals(self) -> None:
        expected = LegalReference(article="5", item="XI")
        for question in (
            "o que diz o inciso XI do art. 5º?",
            "art. 5º, XI",
            "Inciso xi do artigo 5",
        ):
            with self.subTest(question=question):
                self.assertEqual(parse_legal_reference(question), expected)
        self.assertTrue(expected.targets_part)

    def test_thousands_separator_in_the_question(self) -> None:
        for question in ("art. 1.228 do Código Civil", "artigo 1228"):
            with self.subTest(question=question):
                self.assertEqual(
                    parse_legal_reference(question), LegalReference(article="1228")
                )

    def test_word_after_a_comma_is_not_an_item(self) -> None:
        """Revisao M3: "art. 5, vi que..." nao pede o inciso VI."""
        for question in ("art. 5, vi que o texto mudou", "art. 5, li o texto", "art. 5, di"):
            with self.subTest(question=question):
                self.assertEqual(parse_legal_reference(question), LegalReference("5"))
        self.assertEqual(parse_legal_reference("art. 5º, VI"), LegalReference("5", item="VI"))
        self.assertEqual(
            parse_legal_reference("art. 5, vi, da lei"), LegalReference("5", item="VI")
        )

    def test_paragraphs(self) -> None:
        self.assertEqual(
            parse_legal_reference("§ 2º do art. 7"),
            LegalReference(article="7", paragraph="2"),
        )
        self.assertEqual(
            parse_legal_reference("parágrafo único do artigo 3"),
            LegalReference(article="3", paragraph="unico"),
        )

    def test_questions_without_reference(self) -> None:
        for question in (
            "Quanto duram as férias?",
            "Explique o artigo quinto",
            "artes visuais 5 vezes",
            "parte 5 do manual",
            "inciso XI",
        ):
            with self.subTest(question=question):
                self.assertIsNone(parse_legal_reference(question))

    def test_whole_article_does_not_target_a_part(self) -> None:
        self.assertFalse(LegalReference(article="5").targets_part)


class MentionsPartTestCase(unittest.TestCase):
    def test_item_is_found_without_matching_longer_numerals(self) -> None:
        reference = LegalReference(article="5", item="XI")
        self.assertTrue(mentions_part("X - a intimidade; XI - a casa é asilo;", reference))
        self.assertFalse(mentions_part("LXI - ninguém será preso;", reference))
        self.assertFalse(mentions_part("XII - o sigilo;", reference))

    def test_paragraphs(self) -> None:
        self.assertTrue(
            mentions_part("§ 2º Os direitos expressos.", LegalReference("5", paragraph="2"))
        )
        self.assertFalse(
            mentions_part("§ 12 Outro texto.", LegalReference("5", paragraph="2"))
        )
        self.assertTrue(
            mentions_part(
                "Parágrafo único. Vale para todos.",
                LegalReference("3", paragraph="unico"),
            )
        )

    def test_whole_article_mentions_nothing_specific(self) -> None:
        self.assertFalse(mentions_part("I - texto;", LegalReference("5")))


class DescribeItemsTestCase(unittest.TestCase):
    """RN-36: intervalo dos itens que ficaram fora do contexto."""

    def test_range_of_items_in_order(self) -> None:
        texts = ["LXX - o mandado; LXXI - conceder-se-á", "LXXVIII - a razoável duração", "§ 1º As normas"]
        self.assertEqual(describe_items(texts), "LXX a § 1º")

    def test_single_item_and_no_items(self) -> None:
        self.assertEqual(describe_items(["IX - texto"]), "IX")
        self.assertEqual(describe_items(["texto sem marcador"]), "")


if __name__ == "__main__":
    unittest.main()
