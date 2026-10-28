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


if __name__ == "__main__":
    unittest.main()
