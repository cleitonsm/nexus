"""SPEC-018: CT-142 (parte de dominio), acesso ao resumidor e ao documento
pessoal (RN-56, RN-58)."""

from __future__ import annotations

import unittest

from src.domain import AccessPolicy, AuthenticatedUser, Role

ADMIN = AuthenticatedUser(id="admin.nexus", roles=frozenset({Role.ADMIN}))
USER = AuthenticatedUser(id="usuario.rh", roles=frozenset({Role.USER}), groups=frozenset({"rh"}))
OTHER = AuthenticatedUser(id="usuario.financeiro", roles=frozenset({Role.USER}))
NO_ROLE = AuthenticatedUser(id="sem.papel")


class SystemAssistantAccessTestCase(unittest.TestCase):
    def test_every_role_sees_the_system_assistant(self) -> None:
        """RN-56: sem grupo, visivel a todo usuario com papel."""
        for user in (ADMIN, USER, OTHER):
            with self.subTest(user=user.id):
                self.assertTrue(AccessPolicy.can_access_assistant(user, frozenset(), system=True))

    def test_token_without_role_sees_nothing(self) -> None:
        self.assertFalse(AccessPolicy.can_access_assistant(NO_ROLE, frozenset(), system=True))

    def test_common_assistant_rules_are_unchanged(self) -> None:
        """RN-22: assistente comum sem grupo continua so do administrador."""
        self.assertFalse(AccessPolicy.can_access_assistant(USER, frozenset()))
        self.assertTrue(AccessPolicy.can_access_assistant(ADMIN, frozenset()))
        self.assertTrue(AccessPolicy.can_access_assistant(USER, frozenset({"rh"})))


class PersonalDocumentAccessTestCase(unittest.TestCase):
    def test_only_the_conversation_owner(self) -> None:
        """RN-58 e RN-24: nem o administrador le o documento pessoal."""
        self.assertTrue(AccessPolicy.can_use_personal_document(USER, "usuario.rh"))
        self.assertFalse(AccessPolicy.can_use_personal_document(OTHER, "usuario.rh"))
        self.assertFalse(AccessPolicy.can_use_personal_document(ADMIN, "usuario.rh"))

    def test_conversation_without_owner_belongs_to_nobody(self) -> None:
        self.assertFalse(AccessPolicy.can_use_personal_document(USER, None))

    def test_owner_without_role_is_denied(self) -> None:
        self.assertFalse(AccessPolicy.can_use_personal_document(NO_ROLE, "sem.papel"))


if __name__ == "__main__":
    unittest.main()
