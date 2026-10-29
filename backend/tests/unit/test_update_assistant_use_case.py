"""CT-132 (SPEC-017): edicao de nome, descricao e prompt do assistente."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from access_doubles import AccessFixture, admin, curator, make_user
from src.application.use_cases import (
    AssistantNotFoundError,
    ListAssistantsUseCase,
    UpdateAssistantInput,
    UpdateAssistantUseCase,
)
from src.domain import (
    AccessDeniedError,
    Assistant,
    AssistantId,
    AssistantName,
    AssistantProfileValidationError,
    AuditAction,
    LLMCredentialId,
)


class ProfileAssistantRepository:
    """Repositorio em memoria com ``update_profile`` (RN-54)."""

    def __init__(self) -> None:
        self.items: dict[str, Assistant] = {}
        self.update_calls = 0
        self.vanish_on_update = False

    def save(self, assistant: Assistant) -> Assistant:
        self.items[assistant.id.value] = assistant
        return assistant

    def update_profile(self, assistant_id, *, name, description, initial_prompt):
        self.update_calls += 1
        if self.vanish_on_update:
            self.items.pop(assistant_id.value, None)
        current = self.items.get(assistant_id.value)
        if current is None:
            return None
        updated = replace(
            current, name=name, description=description, initial_prompt=initial_prompt
        )
        self.items[assistant_id.value] = updated
        return updated

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)

    def delete(self, assistant_id: AssistantId) -> bool:
        return self.items.pop(assistant_id.value, None) is not None


class UpdateAssistantUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.repo = ProfileAssistantRepository()
        self.repo.save(
            Assistant(
                id=AssistantId("juridico"),
                name=AssistantName("Assistente juridico"),
                description="Contratos",
                initial_prompt="Aja como advogado.",
                llm_credential_id=LLMCredentialId("cred-1"),
                llm_model="gpt-4o-mini",
            )
        )
        self.repo.save(Assistant(id=AssistantId("sem-grupo"), name=AssistantName("Rascunho")))
        self.access.link_assistant("juridico", "juridico")
        self.use_case = UpdateAssistantUseCase(self.repo, self.access.control)

    def update(self, user, assistant_id="juridico", **fields):
        values = {
            "name": "Juridico e Contratos",
            "description": "Contratos e pareceres",
            "initial_prompt": "Responda em topicos.",
        }
        values.update(fields)
        return self.use_case.execute(
            UpdateAssistantInput(user=user, assistant_id=assistant_id, **values)
        )

    def test_admin_updates_the_three_fields_and_keeps_the_rest(self) -> None:
        result = self.update(admin())
        self.assertEqual(result.name, "Juridico e Contratos")
        self.assertEqual(result.initial_prompt, "Responda em topicos.")
        stored = self.repo.items["juridico"]
        self.assertEqual(stored.llm_credential_id, LLMCredentialId("cred-1"))
        self.assertEqual(stored.llm_model, "gpt-4o-mini")
        self.assertEqual(result.groups, ("juridico",))

    def test_curator_of_the_assistant_updates(self) -> None:
        editor = curator("curador-1", "juridico")
        self.update(editor)
        event = self.access.audit.last(AuditAction.ASSISTANT_UPDATED)
        self.assertEqual(event.user_id, "curador-1")

    def test_common_user_and_other_curator_are_denied_and_audited(self) -> None:
        for user in (
            make_user("user-1", groups=("juridico",)),
            curator("curador-2", "financeiro"),
        ):
            with self.subTest(user=user.id):
                with self.assertRaises(AccessDeniedError):
                    self.update(user)
                self.assertEqual(self.access.audit.actions()[-1], AuditAction.ACCESS_DENIED)
        self.assertEqual(self.repo.update_calls, 0)
        self.assertEqual(self.repo.items["juridico"].name.value, "Assistente juridico")

    def test_assistant_without_group_is_admin_only(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self.update(curator("curador-1", "juridico"), assistant_id="sem-grupo")
        self.update(admin(), assistant_id="sem-grupo")

    def test_missing_assistant_is_403_for_curator_and_not_found_for_admin(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self.update(curator("curador-1", "juridico"), assistant_id="nao-existe")
        with self.assertRaises(AssistantNotFoundError):
            self.update(admin(), assistant_id="nao-existe")

    def test_deleted_between_read_and_write_is_not_recreated(self) -> None:
        self.repo.vanish_on_update = True
        with self.assertRaises(AssistantNotFoundError):
            self.update(admin())
        self.assertNotIn("juridico", self.repo.items)
        self.assertNotIn(AuditAction.ASSISTANT_UPDATED, self.access.audit.actions())

    def test_no_change_writes_nothing_and_audits_nothing(self) -> None:
        self.update(
            admin(),
            name=" Assistente juridico ",
            description="Contratos",
            initial_prompt="Aja como advogado.",
        )
        self.assertEqual(self.repo.update_calls, 0)
        self.assertNotIn(AuditAction.ASSISTANT_UPDATED, self.access.audit.actions())

    def test_audit_event_has_digests_and_never_the_text(self) -> None:
        self.update(admin(), description="Contratos")
        event = self.access.audit.last(AuditAction.ASSISTANT_UPDATED)
        details = event.details
        self.assertEqual(details["changed_fields"], ["name", "initial_prompt"])
        self.assertEqual(details["name_before"], "Assistente juridico")
        self.assertEqual(details["name_after"], "Juridico e Contratos")
        self.assertEqual(details["initial_prompt_after"]["length"], len("Responda em topicos."))
        self.assertEqual(len(details["initial_prompt_after"]["sha256"]), 64)
        dumped = json.dumps(details)
        self.assertNotIn("Responda em topicos", dumped)
        self.assertNotIn("Aja como advogado", dumped)

    def test_clearing_the_prompt_stores_none(self) -> None:
        result = self.update(admin(), initial_prompt="   ")
        self.assertIsNone(result.initial_prompt)
        self.assertIsNone(self.repo.items["juridico"].initial_prompt)

    def test_invalid_field_raises_coded_error_without_writing(self) -> None:
        with self.assertRaises(AssistantProfileValidationError) as ctx:
            self.update(admin(), initial_prompt="p" * 4001)
        self.assertEqual(ctx.exception.code, "assistant_prompt_too_long")
        self.assertEqual(self.repo.update_calls, 0)


class PromptVisibilityTests(unittest.TestCase):
    """D5 (RF-111): o prompt so vai para quem pode edita-lo."""

    def test_prompt_hidden_from_common_user_and_shown_to_editors(self) -> None:
        access = AccessFixture()
        repo = ProfileAssistantRepository()
        repo.save(
            Assistant(
                id=AssistantId("juridico"),
                name=AssistantName("Juridico"),
                initial_prompt="Aja como advogado.",
            )
        )
        access.link_assistant("juridico", "juridico")
        listing = ListAssistantsUseCase(repo, access.control)

        common = listing.execute(make_user("user-1", groups=("juridico",)))
        self.assertIsNone(common[0].initial_prompt)
        for editor in (admin(), curator("curador-1", "juridico")):
            with self.subTest(user=editor.id):
                self.assertEqual(listing.execute(editor)[0].initial_prompt, "Aja como advogado.")

    def test_inference_catalog_keeps_the_prompt_but_only_visible_assistants(self) -> None:
        """A D5 vale para a listagem, nao para a escolha automatica (SPEC-017 item 4)."""
        access = AccessFixture()
        repo = ProfileAssistantRepository()
        repo.save(
            Assistant(
                id=AssistantId("juridico"),
                name=AssistantName("Juridico"),
                initial_prompt="Aja como advogado.",
            )
        )
        repo.save(Assistant(id=AssistantId("restrito"), name=AssistantName("Restrito")))
        access.link_assistant("juridico", "juridico")
        access.link_assistant("restrito", "diretoria")

        catalog = ListAssistantsUseCase(repo, access.control).inference_catalog(
            make_user("user-1", groups=("juridico",))
        )

        self.assertEqual([item.id for item in catalog], ["juridico"])
        self.assertEqual(catalog[0].initial_prompt, "Aja como advogado.")
        self.assertEqual(catalog[0].groups, ())


if __name__ == "__main__":
    unittest.main()
