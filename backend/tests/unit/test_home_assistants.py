"""SPEC-016: CT-124, regras de dominio do acesso rapido (RN-47, RN-49, D4, D7, D8)."""

from __future__ import annotations

import unittest

from src.domain import (
    MAX_HOME_ASSISTANTS,
    AssistantId,
    HomeAssistantSelection,
    HomeAssistantsValidationError,
    effective_home_assistants,
)


def ids(*values: str) -> tuple[AssistantId, ...]:
    return tuple(AssistantId(value) for value in values)


def selection(values: tuple[str, ...], default: str) -> HomeAssistantSelection:
    return HomeAssistantSelection(assistant_ids=ids(*values), default_id=AssistantId(default))


class HomeAssistantSelectionTestCase(unittest.TestCase):
    """RN-47: de 1 a MAX, sem repeticao, padrao entre os marcados."""

    def test_limit_is_four(self) -> None:
        self.assertEqual(MAX_HOME_ASSISTANTS, 4)

    def test_one_and_max_are_accepted(self) -> None:
        selection(("a",), "a")
        selection(("a", "b", "c", "d"), "c")

    def test_invalid_selections_are_rejected_with_code(self) -> None:
        cases = (
            ((), "a", "home_assistants_empty"),
            (("a", "b", "c", "d", "e"), "a", "home_assistants_limit"),
            (("a", "b", "a"), "a", "home_assistants_duplicate"),
            (("a", "b"), "c", "home_assistants_default_not_selected"),
        )
        for values, default, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(HomeAssistantsValidationError) as caught:
                    selection(values, default)
                self.assertEqual(caught.exception.code, code)

    def test_validation_error_is_a_domain_error(self) -> None:
        from src.domain import DomainValidationError

        self.assertTrue(issubclass(HomeAssistantsValidationError, DomainValidationError))

    def test_display_order_puts_default_first(self) -> None:
        """D7: padrao primeiro, os outros na ordem de marcacao."""
        chosen = selection(("a", "b", "c"), "b")
        self.assertEqual(chosen.display_order, ids("b", "a", "c"))


class EffectiveHomeAssistantsTestCase(unittest.TestCase):
    """RN-49, D4 e D8."""

    def test_nothing_visible(self) -> None:
        self.assertIsNone(effective_home_assistants(None, ()))
        self.assertIsNone(effective_home_assistants(selection(("a",), "a"), ()))

    def test_never_saved_shows_first_visible(self) -> None:
        """D4: os N primeiros visiveis, o primeiro como padrao."""
        result = effective_home_assistants(None, ids("a", "b", "c", "d", "e"))
        assert result is not None
        self.assertEqual(result.assistant_ids, ids("a", "b", "c", "d"))
        self.assertEqual(result.default_id, AssistantId("a"))
        self.assertFalse(result.customized)

    def test_saved_selection_in_display_order(self) -> None:
        result = effective_home_assistants(
            selection(("c", "a", "d"), "d"), ids("a", "b", "c", "d")
        )
        assert result is not None
        self.assertEqual(result.assistant_ids, ids("d", "c", "a"))
        self.assertEqual(result.default_id, AssistantId("d"))
        self.assertTrue(result.customized)

    def test_lost_assistant_is_filtered(self) -> None:
        result = effective_home_assistants(selection(("a", "b", "c"), "a"), ids("a", "c"))
        assert result is not None
        self.assertEqual(result.assistant_ids, ids("a", "c"))
        self.assertEqual(result.default_id, AssistantId("a"))

    def test_lost_default_falls_to_first_remaining(self) -> None:
        """D8: o primeiro que sobrou vira o padrao efetivo."""
        result = effective_home_assistants(selection(("a", "b", "c"), "b"), ids("a", "c"))
        assert result is not None
        self.assertEqual(result.assistant_ids, ids("a", "c"))
        self.assertEqual(result.default_id, AssistantId("a"))
        self.assertTrue(result.customized)

    def test_everything_lost_falls_back_to_d4(self) -> None:
        result = effective_home_assistants(selection(("x", "y"), "x"), ids("a", "b"))
        assert result is not None
        self.assertEqual(result.assistant_ids, ids("a", "b"))
        self.assertEqual(result.default_id, AssistantId("a"))
        self.assertFalse(result.customized)



PINNED = AssistantId("system-document-summarizer")


def pinned_selection(values: tuple[str, ...], default: str) -> HomeAssistantSelection:
    return HomeAssistantSelection(
        assistant_ids=ids(*values), default_id=AssistantId(default), pinned_id=PINNED
    )


class PinnedHomeAssistantTestCase(unittest.TestCase):
    """SPEC-018: CT-141, cartao fixo do resumidor fora das vagas (RN-57, D1, D2)."""

    def effective(self, saved: HomeAssistantSelection | None, *visible: str):
        result = effective_home_assistants(
            saved, ids(*visible) + (PINNED,), pinned_id=PINNED
        )
        assert result is not None
        return result

    def test_only_the_summarizer_is_visible(self) -> None:
        """Usuario sem assistente da organizacao ainda ve o resumidor."""
        result = effective_home_assistants(None, (PINNED,), pinned_id=PINNED)
        assert result is not None
        self.assertEqual(result.assistant_ids, (PINNED,))
        self.assertEqual(result.default_id, PINNED)
        self.assertEqual(result.pinned_id, PINNED)
        self.assertFalse(result.customized)

    def test_never_customized_puts_summarizer_first_as_default(self) -> None:
        """D2: padrao para quem nunca personalizou; nao ocupa vaga (D1)."""
        result = self.effective(None, "a", "b", "c", "d", "e")
        self.assertEqual(result.assistant_ids, (PINNED,) + ids("a", "b", "c", "d"))
        self.assertEqual(result.default_id, PINNED)
        self.assertFalse(result.customized)

    def test_customized_keeps_the_chosen_default(self) -> None:
        result = self.effective(pinned_selection(("a", "b", "c", "d"), "c"), "a", "b", "c", "d")
        self.assertEqual(result.assistant_ids, (PINNED,) + ids("c", "a", "b", "d"))
        self.assertEqual(result.default_id, AssistantId("c"))
        self.assertTrue(result.customized)

    def test_summarizer_can_be_the_chosen_default(self) -> None:
        result = self.effective(pinned_selection(("a", "b"), PINNED.value), "a", "b", "c")
        self.assertEqual(result.assistant_ids, (PINNED,) + ids("a", "b"))
        self.assertEqual(result.default_id, PINNED)
        self.assertTrue(result.customized)

    def test_lost_default_falls_back_to_the_summarizer(self) -> None:
        """RN-57: antes caia para o primeiro restante (D8 da SPEC-016)."""
        result = self.effective(pinned_selection(("a", "b", "c"), "b"), "a", "c")
        self.assertEqual(result.assistant_ids, (PINNED,) + ids("a", "c"))
        self.assertEqual(result.default_id, PINNED)
        self.assertTrue(result.customized)

    def test_everything_lost_falls_back_to_never_customized(self) -> None:
        result = self.effective(pinned_selection(("x",), "x"), "a")
        self.assertEqual(result.assistant_ids, (PINNED,) + ids("a"))
        self.assertEqual(result.default_id, PINNED)
        self.assertFalse(result.customized)

    def test_pinned_default_survives_losing_every_slot(self) -> None:
        result = self.effective(pinned_selection(("x",), PINNED.value), "a")
        self.assertEqual(result.assistant_ids, (PINNED,))
        self.assertEqual(result.default_id, PINNED)
        self.assertTrue(result.customized)

    def test_summarizer_cannot_take_a_slot(self) -> None:
        with self.assertRaises(HomeAssistantsValidationError) as caught:
            pinned_selection(("a", PINNED.value), "a")
        self.assertEqual(caught.exception.code, "home_assistant_pinned")

    def test_four_slots_besides_the_summarizer(self) -> None:
        chosen = pinned_selection(("a", "b", "c", "d"), PINNED.value)
        self.assertEqual(chosen.display_order, ids("a", "b", "c", "d"))
        self.assertTrue(chosen.default_is_pinned)
        with self.assertRaises(HomeAssistantsValidationError):
            pinned_selection(("a", "b", "c", "d", "e"), "a")

    def test_default_outside_selection_without_pin_is_still_rejected(self) -> None:
        with self.assertRaises(HomeAssistantsValidationError) as caught:
            selection(("a",), PINNED.value)
        self.assertEqual(caught.exception.code, "home_assistants_default_not_selected")


if __name__ == "__main__":
    unittest.main()
