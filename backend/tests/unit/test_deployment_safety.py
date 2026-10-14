"""SPEC-007 fix-4: recusa de segredos padrao fora do ambiente local."""

from __future__ import annotations

import unittest

from src.infrastructure.security import (
    InsecureConfigurationError,
    check_deployment_secrets,
    local_only_warning,
)

DEFAULTS = {
    "NEXUS_SECRETS_KEY": "change-me-in-local-env",
    "QDRANT_API_KEY": "nexus-local",
    "POSTGRES_PASSWORD": "nexus",
    "KEYCLOAK_BACKEND_CLIENT_SECRET": "nexus-backend-dev-secret",
}
STRONG = {
    "NEXUS_SECRETS_KEY": "k" * 40,
    "QDRANT_API_KEY": "q" * 32,
    "POSTGRES_PASSWORD": "p" * 24,
    "KEYCLOAK_BACKEND_CLIENT_SECRET": "s" * 32,
}


class DeploymentSecretsTestCase(unittest.TestCase):
    def test_local_environment_accepts_the_defaults_with_a_warning(self) -> None:
        env = {"APP_ENV": "local", **DEFAULTS}
        self.assertEqual(check_deployment_secrets(env), [])
        self.assertIn("local", local_only_warning(env).lower())

    def test_other_environments_refuse_each_default_secret(self) -> None:
        for name in DEFAULTS:
            env = {"APP_ENV": "production", **STRONG, name: DEFAULTS[name]}
            with self.assertRaises(InsecureConfigurationError, msg=name) as caught:
                check_deployment_secrets(env)
            self.assertIn(name, str(caught.exception))
            self.assertNotIn(DEFAULTS[name], str(caught.exception))

    def test_missing_or_blank_secret_is_refused_outside_local(self) -> None:
        for value in ("", "   "):
            env = {"APP_ENV": "staging", **STRONG, "NEXUS_SECRETS_KEY": value}
            with self.assertRaises(InsecureConfigurationError):
                check_deployment_secrets(env)
        env = {"APP_ENV": "staging", **STRONG}
        del env["NEXUS_SECRETS_KEY"]
        with self.assertRaises(InsecureConfigurationError):
            check_deployment_secrets(env)

    def test_unset_app_env_is_not_local(self) -> None:
        with self.assertRaises(InsecureConfigurationError):
            check_deployment_secrets(dict(DEFAULTS))

    def test_strong_secrets_pass_outside_local(self) -> None:
        self.assertEqual(check_deployment_secrets({"APP_ENV": "production", **STRONG}), [])

    def test_error_lists_every_problem_without_printing_secrets(self) -> None:
        with self.assertRaises(InsecureConfigurationError) as caught:
            check_deployment_secrets({"APP_ENV": "production", **DEFAULTS})
        for name in DEFAULTS:
            self.assertIn(name, str(caught.exception))
        self.assertNotIn("nexus-backend-dev-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
