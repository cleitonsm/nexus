"""Credenciais de LLM no PostgreSQL (SPEC-013, migracao 0010)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain import (
    ConcurrentChangeError,
    DomainValidationError,
    LLMCredential,
    LLMCredentialId,
    LLMCredentialInUseError,
)
from src.infrastructure.llm_credential_mapping import credential_from_row, models_to_json

from .models import LLMCredentialModel
from .transactions import commit_or_rollback

logger = logging.getLogger(__name__)
T = TypeVar("T")

NAME_INDEX = "uq_llm_credentials_name_lower"
DEFAULT_INDEX = "uq_llm_credentials_single_default"
ASSISTANT_FK = "fk_assistants_llm_credential_id"


class PostgresLLMCredentialRepository:
    """RN-37 a RN-39: uma padrao, chave so cifrada, nunca devolvida ao dominio.

    Os indices e a FK do banco fecham as corridas que a conferencia do caso
    de uso nao ve; a violacao vira erro de dominio (409/422), nunca 500.
    """

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
        if model is None:
            return None
        credential = _to_entity(model)
        if credential is None:
            # O chat cai no ambiente sem chave: precisa chamar atencao.
            logger.error(
                "llm_credential.default_invalid", extra={"credential_id": model.id}
            )
        return credential

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
        def write() -> LLMCredentialModel:
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
            return model

        model = self._in_transaction(write)
        self._session.refresh(model)
        saved = _to_entity(model)
        if saved is None:  # pragma: no cover - o dominio ja validou a entrada
            raise ValueError("saved credential failed domain validation.")
        return saved

    def set_default(self, credential_id: LLMCredentialId, *, updated_by: str) -> None:
        """Duas instrucoes na mesma transacao; a linha escolhida fica travada."""

        def write() -> None:
            model = self._session.get(
                LLMCredentialModel, credential_id.value, with_for_update=True
            )
            if model is None:
                raise ConcurrentChangeError("credential was removed concurrently.")
            self._clear_default(except_id=credential_id.value)
            model.is_default = True
            model.updated_by = updated_by
            model.updated_at = datetime.now(UTC)

        self._in_transaction(write)

    def delete(self, credential_id: LLMCredentialId) -> bool:
        """``NOT is_default`` no proprio DELETE: a padrao nunca sai (RN-37/38)."""

        def write() -> int:
            result = self._session.execute(
                delete(LLMCredentialModel).where(
                    LLMCredentialModel.id == credential_id.value,
                    LLMCredentialModel.is_default.is_(False),
                )
            )
            return result.rowcount

        removed = self._in_transaction(write)
        if removed:
            return True
        if self._session.get(LLMCredentialModel, credential_id.value) is not None:
            raise LLMCredentialInUseError(
                "the default credential cannot be removed.", is_default=True
            )
        return False

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

    def _in_transaction(self, write: Callable[[], T]) -> T:
        try:
            result = write()
            commit_or_rollback(self._session)
        except IntegrityError as exc:
            self._session.rollback()
            raise _translate(exc) from exc
        except BaseException:
            self._session.rollback()
            raise
        return result


def _translate(exc: IntegrityError) -> Exception:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None) or ""
    text = f"{constraint} {exc.orig}"
    if NAME_INDEX in text:
        return DomainValidationError("credential name is already in use.")
    if ASSISTANT_FK in text:
        return LLMCredentialInUseError("the credential is used by assistants.")
    if DEFAULT_INDEX in text:
        return ConcurrentChangeError("the default credential changed concurrently.")
    return ConcurrentChangeError("credential changed concurrently.")


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
