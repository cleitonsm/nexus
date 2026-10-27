"""CT-107 (SPEC-013): migracoes 0010 e 0011 e repositorio de credenciais no PostgreSQL.

Mesmo arranjo do CT-49 (``test_migrations``): banco temporario no PostgreSQL
do Compose e Alembic em subprocesso. Sem PostgreSQL, o teste e pulado.
Execute dentro do container do backend. O ciphertext e ficticio: nada aqui
cifra ou decifra chave.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from decimal import Decimal
from uuid import uuid4

from test_migrations import SCRIPT, _admin_engine

try:
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover
    sa = None

from src.domain import (
    PROVIDER_ENDPOINTS,
    DomainValidationError,
    LLMCredentialInUseError,
    Assistant,
    AssistantId,
    AssistantName,
    LLMCredential,
    LLMCredentialId,
    LLMModelOption,
    LLMProvider,
    RetrievalProfile,
)

FAKE_CIPHERTEXT = "gAAAA-ciphertext-ficticio-ct107"
GEMINI_URL = PROVIDER_ENDPOINTS[LLMProvider.GEMINI]


class LLMCredentialsStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = _admin_engine()
        if self.admin is None:
            self.skipTest("PostgreSQL indisponivel")
        self.name = f"nexus_ct107_{uuid4().hex[:10]}"
        with self.admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{self.name}"'))
        self.addCleanup(self._drop)
        base = make_url(
            os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://nexus:nexus@postgres:5432/nexus",
            )
        )
        self.url = base.set(database=self.name)
        self.engine = sa.create_engine(self.url)
        self.addCleanup(self.engine.dispose)

    def _drop(self) -> None:
        self.engine.dispose()
        with self.admin.connect() as connection:
            connection.execute(
                sa.text(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)')
            )
        self.admin.dispose()

    def _alembic(self, action: str, revision: str, **extra_env: str) -> None:
        env = {
            **os.environ,
            "DATABASE_URL": self.url.render_as_string(hide_password=False),
            **extra_env,
        }
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, action, revision],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"{action} {revision}:\n{result.stderr}")

    def _scalar(self, sql: str) -> object:
        with self.engine.connect() as connection:
            return connection.execute(sa.text(sql)).scalar_one_or_none()

    def _seed_spec_008_settings(self, *, with_connection: bool) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO secret_settings (key_name, encrypted_value, "
                    "created_at, updated_at) VALUES ('global_llm_api_key', :c, now(), now())"
                ),
                {"c": FAKE_CIPHERTEXT},
            )
            if with_connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO app_settings (key_name, value, updated_by, updated_at) "
                        "VALUES ('llm_connection', CAST(:v AS json), 'admin', now())"
                    ),
                    {
                        "v": (
                            '{"provider": "gemini", "model": "gemini-3.8-flash", '
                            f'"api_url": "{GEMINI_URL}"}}'
                        )
                    },
                )

    # --- D10: dados da SPEC-008 viram a credencial "Padrão" -----------------

    def test_upgrade_copies_the_global_key_and_connection_to_the_default(self) -> None:
        self._alembic("upgrade", "0009_reassert_audit_guard")
        self._seed_spec_008_settings(with_connection=True)
        self._alembic("upgrade", "0010_llm_credentials")
        with self.engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT name, provider, api_url, default_model, is_default, "
                    "encrypted_key, models FROM llm_credentials"
                )
            ).one()
        self.assertEqual(row.name, "Padrão")
        self.assertEqual(row.provider, "gemini")
        self.assertEqual(row.api_url, GEMINI_URL)
        self.assertEqual(row.default_model, "gemini-3.8-flash")
        self.assertTrue(row.is_default)
        self.assertEqual(row.encrypted_key, FAKE_CIPHERTEXT)
        self.assertEqual(row.models[0]["name"], "gemini-3.8-flash")
        # T9: a 0010 so copia; a 0011 apaga as linhas antigas (D9).
        old_key = "SELECT count(*) FROM secret_settings WHERE key_name = 'global_llm_api_key'"
        old_connection = "SELECT count(*) FROM app_settings WHERE key_name = 'llm_connection'"
        self.assertEqual((self._scalar(old_key), self._scalar(old_connection)), (1, 1))
        self._alembic("upgrade", "head")
        self.assertEqual((self._scalar(old_key), self._scalar(old_connection)), (0, 0))
        self.assertEqual(
            self._scalar("SELECT encrypted_key FROM llm_credentials WHERE is_default"),
            FAKE_CIPHERTEXT,
        )

    def test_upgrade_without_stored_connection_uses_the_environment(self) -> None:
        self._alembic("upgrade", "0009_reassert_audit_guard")
        self._seed_spec_008_settings(with_connection=False)
        self._alembic(
            "upgrade",
            "head",
            LLM_API_URL="https://llm.exemplo.com/v1/chat/completions",
            LLM_MODEL="modelo-ficticio",
        )
        with self.engine.connect() as connection:
            row = connection.execute(
                sa.text("SELECT provider, api_url, default_model FROM llm_credentials")
            ).one()
        self.assertEqual(
            tuple(row),
            ("custom", "https://llm.exemplo.com/v1/chat/completions", "modelo-ficticio"),
        )

    def test_upgrade_without_key_creates_no_credential(self) -> None:
        self._alembic("upgrade", "head")
        self.assertEqual(self._scalar("SELECT count(*) FROM llm_credentials"), 0)

    def test_downgrade_restores_the_spec_008_rows(self) -> None:
        self._alembic("upgrade", "0009_reassert_audit_guard")
        self._seed_spec_008_settings(with_connection=True)
        self._alembic("upgrade", "head")
        self._alembic("downgrade", "0009_reassert_audit_guard")
        self.assertEqual(
            self._scalar(
                "SELECT encrypted_value FROM secret_settings "
                "WHERE key_name = 'global_llm_api_key'"
            ),
            FAKE_CIPHERTEXT,
        )
        stored = self._scalar("SELECT value FROM app_settings WHERE key_name = 'llm_connection'")
        self.assertEqual(stored["provider"], "gemini")
        self.assertEqual(stored["model"], "gemini-3.8-flash")
        self.assertNotIn("llm_credentials", sa.inspect(self.engine).get_table_names())

    # --- RN-37 e RN-38 garantidos pelo banco --------------------------------

    def test_database_rejects_two_defaults_and_removing_a_credential_in_use(self) -> None:
        self._alembic("upgrade", "head")
        insert = (
            "INSERT INTO llm_credentials (id, name, provider, api_url, models, "
            "default_model, is_default, created_at, updated_at) VALUES "
            "(:id, :name, 'openai', 'https://api.openai.com/v1/chat/completions', "
            "CAST('[{\"name\": \"gpt-4o-mini\"}]' AS json), 'gpt-4o-mini', true, now(), now())"
        )
        with self.engine.begin() as connection:
            connection.execute(sa.text(insert), {"id": "c1", "name": "A"})
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(sa.text(insert), {"id": "c2", "name": "B"})
        with self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO assistants (id, name, llm_credential_id) "
                    "VALUES ('a1', 'Juridico', 'c1')"
                )
            )
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM llm_credentials WHERE id = 'c1'"))

    # --- Repositorios --------------------------------------------------------

    def test_repository_round_trip_default_switch_and_key_kept(self) -> None:
        from src.infrastructure.database.llm_credential_repository import (
            PostgresLLMCredentialRepository,
        )
        from src.infrastructure.database.repositories import PostgresAssistantRepository

        self._alembic("upgrade", "head")
        with Session(self.engine) as session:
            repository = PostgresLLMCredentialRepository(session)
            openai = LLMCredential.build(
                credential_id="cred-openai",
                name="OpenAI",
                provider="openai",
                api_url=None,
                models=(
                    LLMModelOption(name="gpt-4o-mini"),
                    LLMModelOption(
                        name="gpt-4o",
                        input_per_1k=Decimal("0.0025"),
                        output_per_1k=Decimal("0.01"),
                    ),
                ),
                default_model="gpt-4o-mini",
                is_default=True,
            )
            saved = repository.save(openai, encrypted_key="cipher-1", updated_by="admin")
            self.assertTrue(saved.key_configured)
            self.assertEqual(saved.model("gpt-4o").input_per_1k, Decimal("0.0025"))

            gemini = LLMCredential.build(
                credential_id="cred-gemini",
                name="Gemini",
                provider="gemini",
                api_url=None,
                models=(LLMModelOption(name="gemini-3.8-flash"),),
                default_model="gemini-3.8-flash",
            )
            repository.save(gemini, encrypted_key=None, updated_by="admin")
            self.assertFalse(repository.get(LLMCredentialId("cred-gemini")).key_configured)

            repository.set_default(LLMCredentialId("cred-gemini"), updated_by="admin")
            self.assertEqual(repository.get_default().id, LLMCredentialId("cred-gemini"))
            self.assertFalse(repository.get(LLMCredentialId("cred-openai")).is_default)

            # encrypted_key=None mantem a chave gravada (rotacao opcional).
            repository.save(
                repository.get(LLMCredentialId("cred-openai")),
                encrypted_key=None,
                updated_by="admin",
            )
            self.assertEqual(
                repository.get_encrypted_key(LLMCredentialId("cred-openai")), "cipher-1"
            )

            assistants = PostgresAssistantRepository(session)
            assistants.save(
                Assistant(
                    id=AssistantId("juridico"),
                    name=AssistantName("Juridico"),
                    llm_credential_id=LLMCredentialId("cred-openai"),
                    llm_model="gpt-4o",
                    retrieval_profile=RetrievalProfile(hybrid_enabled=False, min_score=0.3),
                )
            )
            loaded = assistants.get_by_id(AssistantId("juridico"))
            self.assertEqual(loaded.llm_credential_id, LLMCredentialId("cred-openai"))
            self.assertEqual(loaded.llm_model, "gpt-4o")
            self.assertEqual(
                loaded.retrieval_profile, RetrievalProfile(hybrid_enabled=False, min_score=0.3)
            )
            self.assertEqual(
                [item.name for item in repository.list_all()], ["Gemini", "OpenAI"]
            )

            # O banco fecha as corridas: nome sem diferenciar maiusculas e a padrao.
            clash = LLMCredential.build(
                credential_id="cred-clash",
                name="gemini",
                provider="openai",
                api_url=None,
                models=(LLMModelOption(name="gpt-4o-mini"),),
                default_model="gpt-4o-mini",
            )
            with self.assertRaises(DomainValidationError):
                repository.save(clash, encrypted_key=None, updated_by="admin")
            with self.assertRaises(LLMCredentialInUseError):
                repository.delete(LLMCredentialId("cred-gemini"))
            # Credencial escolhida por assistente: a FK vira erro de dominio.
            with self.assertRaises(LLMCredentialInUseError):
                repository.delete(LLMCredentialId("cred-openai"))
            self.assertEqual(len(repository.list_all()), 2)

            # Atualizacoes por coluna nao se desfazem.
            assistants.update_retrieval_profile(
                AssistantId("juridico"), RetrievalProfile(top_k=8)
            )
            assistants.update_llm_choice(
                AssistantId("juridico"), credential_id=None, model=None
            )
            loaded = assistants.get_by_id(AssistantId("juridico"))
            self.assertEqual(loaded.retrieval_profile, RetrievalProfile(top_k=8))
            self.assertIsNone(loaded.llm_credential_id)


if __name__ == "__main__":
    unittest.main()
