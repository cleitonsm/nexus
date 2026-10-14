"""SPEC-009: grupos informados precisam existir no Keycloak (CT-74 e CT-75)."""

from __future__ import annotations

import unittest

from access_doubles import StaticGroupDirectory

from src.application.services import UnknownGroupsError, ensure_known_groups
from src.domain import DomainValidationError, normalize_groups


class EnsureKnownGroupsTestCase(unittest.TestCase):
    def check(self, directory, *groups: str) -> None:
        ensure_known_groups(normalize_groups(groups), directory)

    def test_unknown_group_is_rejected_with_the_names(self) -> None:
        """CT-74"""
        directory = StaticGroupDirectory("rh", "diretoria")
        with self.assertRaises(UnknownGroupsError) as raised:
            self.check(directory, "rh", "Sem restrição", "financeiro")
        self.assertEqual(raised.exception.groups, ["Sem restrição", "financeiro"])
        self.assertIn("Sem restrição", str(raised.exception))
        self.assertIsInstance(raised.exception, DomainValidationError)

    def test_known_groups_pass_with_or_without_the_leading_slash(self) -> None:
        """CT-75"""
        directory = StaticGroupDirectory("rh", "/diretoria")
        self.check(directory, "/rh", "diretoria")

    def test_match_is_exact_about_case(self) -> None:
        """CT-74: o filtro de acesso compara o nome exato."""
        with self.assertRaises(UnknownGroupsError):
            self.check(StaticGroupDirectory("rh"), "RH")

    def test_no_groups_never_consults_the_directory(self) -> None:
        """CT-75: remover a restricao nao depende do Keycloak."""
        directory = StaticGroupDirectory("rh", available=False)
        self.check(directory)
        self.assertEqual(directory.calls, 0)

    def test_unavailable_directory_accepts_and_logs_a_warning(self) -> None:
        """CT-75"""
        directory = StaticGroupDirectory(available=False)
        with self.assertLogs("src.application.services.group_validation", "WARNING") as logs:
            self.check(directory, "qualquer")
        self.assertIn("groups.validation.skipped", logs.output[0])

    def test_without_a_directory_nothing_is_validated(self) -> None:
        """CT-75: o comando de avaliacao nao usa o diretorio."""
        self.check(None, "qualquer")


if __name__ == "__main__":
    unittest.main()
