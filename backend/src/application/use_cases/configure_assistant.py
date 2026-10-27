"""Modelo de linguagem e parametros de recuperacao do assistente (SPEC-013).

RF-90: credencial e modelo, so pelo administrador (D7). RF-91: parametros de
recuperacao, pelo administrador e pelo curador do assistente (D7). A consulta
mostra o valor efetivo e a origem de cada campo. Toda alteracao vai para a
auditoria com o antes e o depois (RF-94).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.application.services import AccessControl
from src.domain import (
    Assistant,
    AssistantId,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    DomainValidationError,
    LLMConnection,
    LLMCredentialId,
    LLMCredentialRepository,
    RetrievalDefaults,
    RetrievalProfile,
)

from .manage_assistant_access import AssistantNotFoundError
from .manage_llm_credentials import LLMCredentialNotFoundError


@dataclass(frozen=True, slots=True)
class AssistantLLMDTO:
    # O que esta gravado no assistente (vazio = segue a padrao).
    credential_id: str | None
    model: str | None
    # O que vale na proxima pergunta.
    effective_credential_id: str | None
    effective_credential_name: str | None
    effective_provider: str
    effective_model: str
    # "assistant", "default" ou "environment" (RN-40).
    source: str
    # D11: o modelo gravado nao existe na padrao vigente.
    model_falls_back: bool


@dataclass(frozen=True, slots=True)
class RetrievalFieldDTO:
    stored: object | None
    effective: object
    origin: str


@dataclass(frozen=True, slots=True)
class AssistantRetrievalDTO:
    hybrid_enabled: RetrievalFieldDTO
    candidates: RetrievalFieldDTO
    top_k: RetrievalFieldDTO
    min_score: RetrievalFieldDTO
    top_k_clamped: bool


@dataclass(frozen=True, slots=True)
class AssistantRefInput:
    user: AuthenticatedUser
    assistant_id: str


@dataclass(frozen=True, slots=True)
class UpdateAssistantLLMInput:
    user: AuthenticatedUser
    assistant_id: str
    credential_id: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateAssistantRetrievalInput:
    """Substitui o perfil inteiro: campo ``None`` volta ao padrao."""

    user: AuthenticatedUser
    assistant_id: str
    hybrid_enabled: bool | None = None
    candidates: int | None = None
    top_k: int | None = None
    min_score: float | None = None


class _AssistantConfiguration:
    def __init__(
        self,
        *,
        assistants: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._assistants = assistants
        self._access = access_control

    def _get(self, assistant_id: str) -> Assistant:
        assistant = self._assistants.get_by_id(AssistantId(assistant_id))
        if assistant is None:
            raise AssistantNotFoundError("assistant not found.")
        return assistant


class GetAssistantLLMUseCase(_AssistantConfiguration):
    """RF-90: o gravado e o efetivo, sem a chave."""

    def __init__(
        self,
        *,
        assistants: AssistantRepository,
        access_control: AccessControl,
        credentials: LLMCredentialRepository,
        environment: LLMConnection,
    ) -> None:
        super().__init__(assistants=assistants, access_control=access_control)
        self._credentials = credentials
        self._environment = environment

    def execute(self, data: AssistantRefInput) -> AssistantLLMDTO:
        assistant = self._get(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant.id, AuditAction.ASSISTANT_LLM_CHANGED
        )
        return describe_assistant_llm(
            assistant, credentials=self._credentials, environment=self._environment
        )


class UpdateAssistantLLMUseCase(_AssistantConfiguration):
    """RF-90 e D11: modelo da credencial escolhida ou da padrao vigente."""

    def __init__(
        self,
        *,
        assistants: AssistantRepository,
        access_control: AccessControl,
        credentials: LLMCredentialRepository,
        environment: LLMConnection,
    ) -> None:
        super().__init__(assistants=assistants, access_control=access_control)
        self._credentials = credentials
        self._environment = environment

    def execute(self, data: UpdateAssistantLLMInput) -> AssistantLLMDTO:
        self._access.require_llm_configuration(data.user, AuditAction.ASSISTANT_LLM_CHANGED)
        assistant = self._get(data.assistant_id)
        credential_id = (data.credential_id or "").strip() or None
        model = (data.model or "").strip() or None
        if credential_id is not None:
            credential = self._credentials.get(LLMCredentialId(credential_id))
            if credential is None:
                raise LLMCredentialNotFoundError("credential not found.")
        else:
            credential = self._credentials.get_default()
            if credential is None and model is not None:
                raise DomainValidationError(
                    "a model needs a credential: there is no default credential."
                )
        if model is not None and credential is not None:
            # Escolhida: o modelo precisa estar nela. Seguindo a padrao: na
            # padrao vigente, ao gravar (D11); depois pode recuar.
            credential.model(model)
        updated = replace(
            assistant,
            llm_credential_id=LLMCredentialId(credential_id) if credential_id else None,
            llm_model=model,
        )
        saved = self._assistants.save(updated)
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_LLM_CHANGED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=saved.id.value,
            details={
                "assistant_id": saved.id.value,
                "credential_id": credential_id,
                "model": model,
                "previous_credential_id": (
                    assistant.llm_credential_id.value
                    if assistant.llm_credential_id
                    else None
                ),
                "previous_model": assistant.llm_model,
            },
        )
        return describe_assistant_llm(
            saved, credentials=self._credentials, environment=self._environment
        )


class GetAssistantRetrievalUseCase(_AssistantConfiguration):
    """RF-91: valor gravado, efetivo e origem de cada parametro."""

    def __init__(
        self,
        *,
        assistants: AssistantRepository,
        access_control: AccessControl,
        defaults: RetrievalDefaults,
    ) -> None:
        super().__init__(assistants=assistants, access_control=access_control)
        self._defaults = defaults

    def execute(self, data: AssistantRefInput) -> AssistantRetrievalDTO:
        assistant = self._get(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant.id, AuditAction.ASSISTANT_RETRIEVAL_SETTINGS_CHANGED
        )
        return describe_retrieval(assistant.retrieval_profile, self._defaults)


class UpdateAssistantRetrievalUseCase(_AssistantConfiguration):
    """RF-91, D6 e T3: faixas e top_k <= candidatos efetivos ao gravar."""

    def __init__(
        self,
        *,
        assistants: AssistantRepository,
        access_control: AccessControl,
        defaults: RetrievalDefaults,
    ) -> None:
        super().__init__(assistants=assistants, access_control=access_control)
        self._defaults = defaults

    def execute(self, data: UpdateAssistantRetrievalInput) -> AssistantRetrievalDTO:
        assistant = self._get(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant.id, AuditAction.ASSISTANT_RETRIEVAL_SETTINGS_CHANGED
        )
        profile = RetrievalProfile(
            hybrid_enabled=data.hybrid_enabled,
            candidates=data.candidates,
            top_k=data.top_k,
            min_score=data.min_score,
        )
        profile.validate_against(self._defaults)
        saved = self._assistants.save(replace(assistant, retrieval_profile=profile))
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_RETRIEVAL_SETTINGS_CHANGED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=saved.id.value,
            details={
                "assistant_id": saved.id.value,
                "settings": profile.as_dict(),
                "previous_settings": assistant.retrieval_profile.as_dict(),
            },
        )
        return describe_retrieval(saved.retrieval_profile, self._defaults)


def describe_assistant_llm(
    assistant: Assistant,
    *,
    credentials: LLMCredentialRepository,
    environment: LLMConnection,
) -> AssistantLLMDTO:
    """Como ``resolve_llm_for_assistant``, sem decifrar a chave."""
    stored_id = assistant.llm_credential_id.value if assistant.llm_credential_id else None
    credential = None
    source = "environment"
    if assistant.llm_credential_id is not None:
        credential = credentials.get(assistant.llm_credential_id)
        source = "assistant"
    if credential is None:
        credential = credentials.get_default()
        source = "default" if credential is not None else "environment"
    if credential is None:
        return AssistantLLMDTO(
            credential_id=stored_id,
            model=assistant.llm_model,
            effective_credential_id=None,
            effective_credential_name=None,
            effective_provider=environment.provider.value,
            effective_model=environment.model,
            source=source,
            model_falls_back=False,
        )
    option, fell_back = credential.model_with_fallback(assistant.llm_model)
    return AssistantLLMDTO(
        credential_id=stored_id,
        model=assistant.llm_model,
        effective_credential_id=credential.id.value,
        effective_credential_name=credential.name,
        effective_provider=credential.provider.value,
        effective_model=option.name,
        source=source,
        model_falls_back=fell_back,
    )


def describe_retrieval(
    profile: RetrievalProfile, defaults: RetrievalDefaults
) -> AssistantRetrievalDTO:
    resolved = profile.resolve(defaults)

    def field_dto(name: str) -> RetrievalFieldDTO:
        return RetrievalFieldDTO(
            stored=getattr(profile, name),
            effective=getattr(resolved, name),
            origin=resolved.origin(name).value,
        )

    return AssistantRetrievalDTO(
        hybrid_enabled=field_dto("hybrid_enabled"),
        candidates=field_dto("candidates"),
        top_k=field_dto("top_k"),
        min_score=field_dto("min_score"),
        top_k_clamped=resolved.top_k_clamped,
    )
