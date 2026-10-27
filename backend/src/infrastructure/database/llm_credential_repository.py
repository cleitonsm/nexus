"""Credenciais de LLM no PostgreSQL (SPEC-013, migracao 0010)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.domain import LLMCredential, LLMCredentialId

from src.infrastructure.llm_credential_mapping import credential_from_row, models_to_json
from .models import LLMCredentialModel
from .transactions import commit_or_rollback


class PostgresLLMCredentialRepository:
    """RN-37 a RN-39: uma padrao, chave so cifrada, nunca devolvida ao dominio."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[LLMCredential]:
        stmt = select(LLMCredentialModel).order_by(
            LLMCredentialModel.is_default.desc(), LLMCredentialModel.name
        )
        return [
            credential
            for model in self._session.scalars(stmt).all()
            if (credential := _to_entity(model)) is not None
        ]

    def get(self, credential_id: LLMCredentialId) -> LLMCredential | None:
        model = self._session.get(LLMCredentialModel, credential_id.value)
        return None if model is None else _to_entity(model)

    def get_default(self) -> LLMCredential | None:
        stmt = select(LLMCredentialModel).where(LLMCredentialModel.is_default.is_(True))
        model = self._session.scalars(stmt).first()
        return None if model is None else _to_entity(model)

    def get_encrypted_key(self, credential_id: LLMCredentialId) -> str | None:
        model = self._session.get(LLMCredentialModel, credential_id.value)
        return None if model is None else model.encrypted_key

    def save(
        self,
        credential: LLMCredential,
        *,
        encrypted_key: str | None,
        updated_by: str,
    ) -> LLMCredential:
        now = datetime.now(UTC)
        if credential.is_default:
            self._clear_default(except_id=credential.id.value)
        model = self._session.get(LLMCredentialModel, credential.id.value)
        if model is None:
            model = LLMCredentialModel(
                id=credential.id.value,
                created_by=updated_by,
                created_at=now,
            )
            self._session.add(model)
        model.name = credential.name
        model.provider = credential.provider.value
        model.api_url = credential.api_url
        model.models = models_to_json(credential.models)
        model.default_model = credential.default_model
        model.is_default = credential.is_default
        if encrypted_key is not None:
            model.encrypted_key = encrypted_key
        model.updated_by = updated_by
        model.updated_at = now
        commit_or_rollback(self._session)
        self._session.refresh(model)
        saved = _to_entity(model)
        if saved is None:  # pragma: no cover - o dominio ja validou a entrada
            raise ValueError("saved credential failed domain validation.")
        return saved

    def set_default(self, credential_id: LLMCredentialId, *, updated_by: str) -> None:
        """Duas instrucoes na mesma transacao: o indice parcial nunca ve duas padrao."""
        model = self._session.get(LLMCredentialModel, credential_id.value)
        if model is None:
            raise LookupError("credential not found.")
        self._clear_default(except_id=credential_id.value)
        model.is_default = True
        model.updated_by = updated_by
        model.updated_at = datetime.now(UTC)
        commit_or_rollback(self._session)

    def delete(self, credential_id: LLMCredentialId) -> bool:
        model = self._session.get(LLMCredentialModel, credential_id.value)
        if model is None:
            return False
        self._session.delete(model)
        commit_or_rollback(self._session)
        return True

    def _clear_default(self, *, except_id: str) -> None:
        self._session.execute(
            update(LLMCredentialModel)
            .where(
                LLMCredentialModel.is_default.is_(True),
                LLMCredentialModel.id != except_id,
            )
            .values(is_default=False)
        )
        self._session.flush()


def _to_entity(model: LLMCredentialModel) -> LLMCredential | None:
    return credential_from_row(
        credential_id=model.id,
        name=model.name,
        provider=model.provider,
        api_url=model.api_url,
        models=model.models,
        default_model=model.default_model,
        is_default=model.is_default,
        encrypted_key=model.encrypted_key,
    )
