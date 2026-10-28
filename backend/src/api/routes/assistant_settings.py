"""Rotas da SPEC-013: modelo de linguagem e recuperacao do assistente (RF-90, RF-91)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import (
    get_access_control,
    get_assistant_repository,
    get_current_user,
    get_llm_connection_default,
    get_llm_credential_repository,
    get_retrieval_defaults,
)
from src.api.schemas.llm_credentials import (
    AssistantLLMRequest,
    AssistantLLMResponse,
    AssistantRetrievalRequest,
    AssistantRetrievalResponse,
    RetrievalFieldResponse,
    RetrievalLimitsResponse,
)
from src.application.services import AccessControl
from src.application.use_cases import (
    AssistantLLMDTO,
    AssistantRefInput,
    AssistantRetrievalDTO,
    GetAssistantLLMUseCase,
    GetAssistantRetrievalUseCase,
    LLMCredentialNotFoundError,
    RetrievalFieldDTO,
    UpdateAssistantLLMInput,
    UpdateAssistantLLMUseCase,
    UpdateAssistantRetrievalInput,
    UpdateAssistantRetrievalUseCase,
)
from src.application.use_cases.manage_assistant_access import AssistantNotFoundError
from src.domain import (
    MAX_CANDIDATES,
    MAX_TOP_K,
    MIN_CANDIDATES,
    MIN_SCORE_CEILING,
    MIN_SCORE_FLOOR,
    MIN_TOP_K,
    AssistantRepository,
    AuthenticatedUser,
    DomainValidationError,
    LLMConnection,
    LLMCredentialRepository,
    RetrievalDefaults,
)

router = APIRouter(
    prefix="/assistants",
    tags=["assistants"],
    dependencies=[Depends(get_current_user)],
)

LIMITS = RetrievalLimitsResponse(
    candidates=(MIN_CANDIDATES, MAX_CANDIDATES),
    top_k=(MIN_TOP_K, MAX_TOP_K),
    min_score=(MIN_SCORE_FLOOR, MIN_SCORE_CEILING),
)


@router.get("/{assistant_id}/llm", response_model=AssistantLLMResponse)
def get_assistant_llm(
    assistant_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistants: AssistantRepository = Depends(get_assistant_repository),
    credentials: LLMCredentialRepository = Depends(get_llm_credential_repository),
    environment: LLMConnection = Depends(get_llm_connection_default),
) -> AssistantLLMResponse:
    use_case = GetAssistantLLMUseCase(
        assistants=assistants,
        access_control=access_control,
        credentials=credentials,
        environment=environment,
    )
    try:
        result = use_case.execute(AssistantRefInput(user=user, assistant_id=assistant_id))
    except AssistantNotFoundError as exc:
        raise _not_found("assistant") from exc
    return _llm(result)


@router.put("/{assistant_id}/llm", response_model=AssistantLLMResponse)
def update_assistant_llm(
    assistant_id: str,
    payload: AssistantLLMRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistants: AssistantRepository = Depends(get_assistant_repository),
    credentials: LLMCredentialRepository = Depends(get_llm_credential_repository),
    environment: LLMConnection = Depends(get_llm_connection_default),
) -> AssistantLLMResponse:
    use_case = UpdateAssistantLLMUseCase(
        assistants=assistants,
        access_control=access_control,
        credentials=credentials,
        environment=environment,
    )
    try:
        result = use_case.execute(
            UpdateAssistantLLMInput(
                user=user,
                assistant_id=assistant_id,
                credential_id=payload.credential_id,
                model=payload.model,
            )
        )
    except AssistantNotFoundError as exc:
        raise _not_found("assistant") from exc
    except LLMCredentialNotFoundError as exc:
        # A credencial informada no corpo nao existe: entrada invalida.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "llm_credential_not_found", "message": "credential not found"},
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _llm(result)


@router.get("/{assistant_id}/retrieval-settings", response_model=AssistantRetrievalResponse)
def get_assistant_retrieval(
    assistant_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistants: AssistantRepository = Depends(get_assistant_repository),
    defaults: RetrievalDefaults = Depends(get_retrieval_defaults),
) -> AssistantRetrievalResponse:
    use_case = GetAssistantRetrievalUseCase(
        assistants=assistants, access_control=access_control, defaults=defaults
    )
    try:
        result = use_case.execute(AssistantRefInput(user=user, assistant_id=assistant_id))
    except AssistantNotFoundError as exc:
        raise _not_found("assistant") from exc
    return _retrieval(result)


@router.put("/{assistant_id}/retrieval-settings", response_model=AssistantRetrievalResponse)
def update_assistant_retrieval(
    assistant_id: str,
    payload: AssistantRetrievalRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistants: AssistantRepository = Depends(get_assistant_repository),
    defaults: RetrievalDefaults = Depends(get_retrieval_defaults),
) -> AssistantRetrievalResponse:
    use_case = UpdateAssistantRetrievalUseCase(
        assistants=assistants, access_control=access_control, defaults=defaults
    )
    try:
        result = use_case.execute(
            UpdateAssistantRetrievalInput(
                user=user,
                assistant_id=assistant_id,
                hybrid_enabled=payload.hybrid_enabled,
                candidates=payload.candidates,
                top_k=payload.top_k,
                min_score=payload.min_score,
            )
        )
    except AssistantNotFoundError as exc:
        raise _not_found("assistant") from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _retrieval(result)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _llm(result: AssistantLLMDTO) -> AssistantLLMResponse:
    return AssistantLLMResponse(
        credential_id=result.credential_id,
        model=result.model,
        effective_credential_id=result.effective_credential_id,
        effective_credential_name=result.effective_credential_name,
        effective_provider=result.effective_provider,
        effective_model=result.effective_model,
        source=result.source,
        model_falls_back=result.model_falls_back,
    )


def _field(item: RetrievalFieldDTO) -> RetrievalFieldResponse:
    return RetrievalFieldResponse(
        stored=item.stored,  # type: ignore[arg-type]
        effective=item.effective,  # type: ignore[arg-type]
        origin=item.origin,
    )


def _retrieval(result: AssistantRetrievalDTO) -> AssistantRetrievalResponse:
    return AssistantRetrievalResponse(
        hybrid_enabled=_field(result.hybrid_enabled),
        candidates=_field(result.candidates),
        top_k=_field(result.top_k),
        min_score=_field(result.min_score),
        top_k_clamped=result.top_k_clamped,
        limits=LIMITS,
    )
