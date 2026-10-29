"""CT-131 e CT-133 (SPEC-017): campos do assistente e instrucao de sistema."""

import unittest

from src.application.services import build_answer_instruction
from src.application.services.grounded_answer import (
    CITATION_INSTRUCTION,
    DEFAULT_ANSWER_INSTRUCTION,
    FORMAT_INSTRUCTION,
)
from src.domain import (
    ASSISTANT_DESCRIPTION_TOO_LONG,
    ASSISTANT_NAME_REQUIRED,
    ASSISTANT_NAME_TOO_LONG,
    ASSISTANT_PROMPT_TOO_LONG,
    MAX_ASSISTANT_DESCRIPTION,
    MAX_ASSISTANT_NAME,
    MAX_ASSISTANT_PROMPT,
    AssistantProfileValidationError,
    DomainValidationError,
    assistant_profile_changes,
    build_assistant_profile,
    normalize_optional_text,
)


class AssistantProfileTests(unittest.TestCase):
    """CT-131: RN-51, D3 e D4."""

    def assert_code(self, code: str, **fields: object) -> None:
        values = {"name": "Juridico", "description": None, "initial_prompt": None}
        values.update(fields)
        with self.assertRaises(AssistantProfileValidationError) as ctx:
            build_assistant_profile(**values)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.code, code)
        self.assertIsInstance(ctx.exception, DomainValidationError)

    def test_limits_are_the_approved_ones(self) -> None:
        self.assertEqual(
            (MAX_ASSISTANT_NAME, MAX_ASSISTANT_DESCRIPTION, MAX_ASSISTANT_PROMPT),
            (80, 500, 4000),
        )

    def test_normalizes_spaces_and_empty_text(self) -> None:
        profile = build_assistant_profile("  Juridico  ", "   ", "\n\t")
        self.assertEqual(profile.name.value, "Juridico")
        self.assertIsNone(profile.description)
        self.assertIsNone(profile.initial_prompt)
        self.assertIsNone(normalize_optional_text(None))
        self.assertEqual(normalize_optional_text("  x  "), "x")

    def test_name_required_and_limit(self) -> None:
        self.assert_code(ASSISTANT_NAME_REQUIRED, name="   ")
        self.assert_code(ASSISTANT_NAME_REQUIRED, name="")
        build_assistant_profile("n" * MAX_ASSISTANT_NAME, None, None)
        self.assert_code(ASSISTANT_NAME_TOO_LONG, name="n" * (MAX_ASSISTANT_NAME + 1))

    def test_description_limit(self) -> None:
        build_assistant_profile("A", "d", None)
        build_assistant_profile("A", "d" * MAX_ASSISTANT_DESCRIPTION, None)
        self.assert_code(
            ASSISTANT_DESCRIPTION_TOO_LONG,
            description="d" * (MAX_ASSISTANT_DESCRIPTION + 1),
        )

    def test_prompt_limit_counts_after_trimming(self) -> None:
        build_assistant_profile("A", None, "p" * MAX_ASSISTANT_PROMPT)
        build_assistant_profile("A", None, "  " + "p" * MAX_ASSISTANT_PROMPT + "  ")
        self.assert_code(
            ASSISTANT_PROMPT_TOO_LONG,
            initial_prompt="p" * (MAX_ASSISTANT_PROMPT + 1),
        )

    def test_error_message_never_echoes_the_text(self) -> None:
        secret_like = "INSTRUCAO-" + "x" * MAX_ASSISTANT_PROMPT
        with self.assertRaises(AssistantProfileValidationError) as ctx:
            build_assistant_profile("A", None, secret_like)
        self.assertNotIn("INSTRUCAO", str(ctx.exception))

    def test_changes_lists_only_changed_fields(self) -> None:
        before = build_assistant_profile("A", "d", "p")
        self.assertEqual(assistant_profile_changes(before, before), ())
        self.assertEqual(
            assistant_profile_changes(before, build_assistant_profile(" A ", "d ", "p")),
            (),
        )
        self.assertEqual(
            assistant_profile_changes(before, build_assistant_profile("B", None, "q")),
            ("name", "description", "initial_prompt"),
        )


class EditedPromptInstructionTests(unittest.TestCase):
    """CT-133: RF-109 e D4; o prompt editado nao desliga formato nem citacao."""

    def test_edited_prompt_comes_first_and_keeps_the_fixed_rules(self) -> None:
        instruction = build_answer_instruction("Responda em topicos.")
        self.assertTrue(instruction.startswith("Responda em topicos."))
        self.assertIn(FORMAT_INSTRUCTION, instruction)
        self.assertIn(CITATION_INSTRUCTION, instruction)

    def test_cleared_prompt_falls_back_to_the_default(self) -> None:
        instruction = build_answer_instruction(None)
        self.assertTrue(instruction.startswith(DEFAULT_ANSWER_INSTRUCTION))
        self.assertIn(CITATION_INSTRUCTION, instruction)


if __name__ == "__main__":
    unittest.main()
