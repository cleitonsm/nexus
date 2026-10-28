"""SPEC-016: CT-125, casos de uso do acesso rapido (RN-48, RF-106, D4)."""

from __future__ import annotations

import unittest

from src.application.use_cases import (
    GetHomeAssistantsUseCase,
    SetHomeAssistantsInput,
    SetHomeAssistantsUseCase,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    HomeAssistantSelection,
    HomeAssistantsValidationError,
)
from tests.unit.access_doubles import AccessFixture, make_user


class _Assistants:
    def __init__(self, *ids: str) -> None:
        self.items = [Assistant(id=AssistantId(item), name=AssistantName(item)) for item in ids]

    def list_all(self) -> list[Assistant]:
        return list(self.items)


class _Preferences:
    def __init__(self) -> None:
        self.saved: dict[str, HomeAssistantSelection] = {}

    def get(self, owner_user_id: str) -> HomeAssistantSelection | None:
        return self.saved.get(owner_user_id)

    def replace(self, owner_user_id: str, selection: HomeAssistantSelection) -> None:
        self.saved[owner_user_id] = selection


class HomeAssistantsUseCasesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        for assistant_id in ("normativo", "juridico", "financeiro", "rh", "ti"):
            self.access.link_assistant(assistant_id, "todos")
        self.access.link_assistant("restrito", "diretoria")
        self.assistants = _Assistants("normativo", "juridico", "financeiro", "rh", "ti", "restrito")
        self.preferences = _Preferences()
        deps = {
            "preferences": self.preferences,
            "assistants": self.assistants,
            "access_control": self.access.control,
        }
        self.get = GetHomeAssistantsUseCase(**deps)
        self.set = SetHomeAssistantsUseCase(**deps)
        self.ana = make_user("ana", groups=("todos",))
        self.bruno = make_user("bruno", groups=("todos",))

    def _save(self, user, ids: tuple[str, ...], default: str):
        return self.set.execute(SetHomeAssistantsInput(user, ids, default))

    def test_never_saved_shows_first_four_visible(self) -> None:
        result = self.get.execute(self.ana)
        self.assertEqual(result.assistant_ids, ("normativo", "juridico", "financeiro", "rh"))
        self.assertEqual(result.default_assistant_id, "normativo")
        self.assertEqual(result.max, 4)
        self.assertFalse(result.customized)

    def test_save_and_read_back(self) -> None:
        saved = self._save(self.ana, ("juridico", "financeiro"), "financeiro")
        self.assertEqual(saved.assistant_ids, ("financeiro", "juridico"))
        read = self.get.execute(self.ana)
        self.assertEqual(read, saved)
        self.assertTrue(read.customized)

    def test_choice_is_personal(self) -> None:
        """RF-106: Bruno nunca ve a escolha de Ana."""
        self._save(self.ana, ("ti",), "ti")
        self.assertFalse(self.get.execute(self.bruno).customized)
        self.assertIn("ana", self.preferences.saved)
        self.assertNotIn("bruno", self.preferences.saved)

    def test_inaccessible_and_missing_get_same_error(self) -> None:
        """RN-48."""
        for assistant_id in ("restrito", "nao-existe"):
            with self.subTest(assistant_id=assistant_id):
                with self.assertRaises(HomeAssistantsValidationError) as caught:
                    self._save(self.ana, ("normativo", assistant_id), "normativo")
                self.assertEqual(caught.exception.code, "assistant_not_available")
        self.assertEqual(self.preferences.saved, {})

    def test_denial_is_not_audited(self) -> None:
        """RN-50: preferencia pessoal nao entra na trilha de auditoria."""
        with self.assertRaises(HomeAssistantsValidationError):
            self._save(self.ana, ("restrito",), "restrito")
        self._save(self.ana, ("rh",), "rh")
        self.assertEqual(self.access.audit.events, [])

    def test_blank_id_is_not_available(self) -> None:
        with self.assertRaises(HomeAssistantsValidationError) as caught:
            self._save(self.ana, ("  ",), "  ")
        self.assertEqual(caught.exception.code, "assistant_not_available")

    def test_rule_errors_keep_their_code(self) -> None:
        with self.assertRaises(HomeAssistantsValidationError) as caught:
            self._save(self.ana, ("normativo", "juridico", "financeiro", "rh", "ti"), "ti")
        self.assertEqual(caught.exception.code, "home_assistants_limit")

    def test_lost_group_filters_saved_choice(self) -> None:
        """D8: perder o grupo filtra; a linha continua gravada."""
        self._save(self.ana, ("juridico", "normativo"), "juridico")
        self.access.link_assistant("juridico", "outro")
        result = self.get.execute(self.ana)
        self.assertEqual(result.assistant_ids, ("normativo",))
        self.assertEqual(result.default_assistant_id, "normativo")
        self.assertEqual(len(self.preferences.saved["ana"].assistant_ids), 2)

    def test_user_without_assistants(self) -> None:
        result = self.get.execute(make_user("zeca", groups=("nenhum",)))
        self.assertEqual(result.assistant_ids, ())
        self.assertIsNone(result.default_assistant_id)

    def test_admin_can_pick_assistant_without_group(self) -> None:
        self.assistants.items.append(
            Assistant(id=AssistantId("sem-grupo"), name=AssistantName("sem-grupo"))
        )
        admin = make_user("adm", roles=("nexus-admin",))
        result = self._save(admin, ("sem-grupo",), "sem-grupo")
        self.assertEqual(result.default_assistant_id, "sem-grupo")


if __name__ == "__main__":
    unittest.main()
