from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import (
    get_access_control,
    get_audit_log_repository,
    get_configured_llm_model,
    get_current_user,
    get_secret_cipher,
    get_secret_settings_repository,
    get_usage_record_repository,
    get_usage_settings,
    get_usage_settings_repository,
)
from src.api.schemas import (
    ApiKeyStatusResponse,
    ApiKeyTestResponse,
    AuditEventResponse,
    SaveApiKeyRequest,
    UsageLimitsRequest,
    UsageLimitsResponse,
    UsageReportResponse,
    UsageSummaryResponse,
)
from src.application.dto import UsageLimitsDTO, UsageSummaryDTO
from src.application.services import AccessControl, UsageSettings
from src.application.use_cases import (
    GetGlobalApiKeyStatusUseCase,
    GetGlobalApiKeyValueUseCase,
    ListAuditEventsInput,
    ListAuditEventsUseCase,
    GetUsageLimitsUseCase,
    GetUsageReportInput,
    GetUsageReportUseCase,
    SaveGlobalApiKeyInput,
    SaveGlobalApiKeyUseCase,
    UpdateUsageLimitsInput,
    UpdateUsageLimitsUseCase,
)
from src.domain import (
    AuditAction,
    AuditLogRepository,
    AuditResource,
    AuthenticatedUser,
    DomainValidationError,
    UsageRecordRepository,
    UsageSettingsRepository,
)
from src.infrastructure.database import PostgresSecretSettingsRepository
from src.infrastructure.llm import HttpChatCompletionsLLM
from src.infrastructure.secrets import FernetSecretCipher

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],
)

logger = logging.getLogger(__name__)


@router.get("/api-key/status", response_model=ApiKeyStatusResponse)
def get_api_key_status(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
) -> ApiKeyStatusResponse:
    result = GetGlobalApiKeyStatusUseCase(
        secret_repository=secret_repository,
        access_control=access_control,
    ).execute(user)
    return ApiKeyStatusResponse(configured=result.configured)


@router.post(
    "/api-key",
    response_model=ApiKeyStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_api_key(
    payload: SaveApiKeyRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
) -> ApiKeyStatusResponse:
    use_case = SaveGlobalApiKeyUseCase(
        secret_repository=secret_repository,
        secret_cipher=secret_cipher,
        access_control=access_control,
    )
    try:
        result = use_case.execute(
            SaveGlobalApiKeyInput(user=user, api_key=payload.api_key)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ApiKeyStatusResponse(configured=result.configured)


@router.post("/api-key/test", response_model=ApiKeyTestResponse)
def test_api_key(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
) -> ApiKeyTestResponse:
    access_control.require_llm_configuration(user, AuditAction.LLM_API_KEY_TESTED)
    api_key = GetGlobalApiKeyValueUseCase(
        secret_repository=secret_repository,
        secret_cipher=secret_cipher,
    ).execute()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Global LLM API key is not configured. "
                "Set it in /admin/api-key first."
            ),
        )

    model = get_configured_llm_model()
    api_url = os.getenv(
        "LLM_API_URL",
        "https://api.openai.com/v1/chat/completions",
    )
    llm_gateway = HttpChatCompletionsLLM(
        api_url=api_url,
        model=model,
        api_key=api_key,
        timeout_seconds=15.0,
    )
    access_control.audit(
        user,
        AuditAction.LLM_API_KEY_TESTED,
        resource_type=AuditResource.SETTINGS,
        details={"llm_model": model},
    )
    try:
        answer = llm_gateway.generate(
            prompt=(
                "Teste de conectividade do Nexus. "
                "Responda apenas: OK"
            ),
            context_chunks=[],
            conversation_history=[],
        )
    except (RuntimeError, ValueError) as exc:
        logger.warning(
            "admin.llm_test.failed",
            extra={"llm_model": model},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha na comunicação com a LLM: {str(exc)}",
        ) from exc

    return ApiKeyTestResponse(
        ok=True,
        model=model,
        message="Comunicacao com a LLM validada usando a API key armazenada.",
        response_preview=answer[:200],
    )


@router.get("/usage", response_model=UsageReportResponse)
def get_usage_report(
    occurred_from: datetime | None = Query(default=None, alias="from"),
    occurred_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    record_repository: UsageRecordRepository = Depends(get_usage_record_repository),
    settings: UsageSettings = Depends(get_usage_settings),
) -> UsageReportResponse:
    """RF-57: tokens e custo estimado por usuario e por conversa."""
    try:
        report = GetUsageReportUseCase(
            record_repository=record_repository,
            access_control=access_control,
            settings=settings,
        ).execute(
            GetUsageReportInput(
                user=user,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                limit=limit,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return UsageReportResponse(
        occurred_from=report.occurred_from,
        occurred_to=report.occurred_to,
        currency=report.currency,
        model=report.model,
        by_user=[_usage_summary(item) for item in report.by_user],
        by_conversation=[_usage_summary(item) for item in report.by_conversation],
        total_questions=report.total_questions,
        total_input_tokens=report.total_input_tokens,
        total_output_tokens=report.total_output_tokens,
        total_estimated_cost=report.total_estimated_cost,
    )


@router.get("/usage-limits", response_model=UsageLimitsResponse)
def get_usage_limits(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    settings_repository: UsageSettingsRepository = Depends(
        get_usage_settings_repository
    ),
    settings: UsageSettings = Depends(get_usage_settings),
) -> UsageLimitsResponse:
    result = GetUsageLimitsUseCase(
        settings_repository=settings_repository,
        access_control=access_control,
        settings=settings,
    ).execute(user)
    return _limits(result)


@router.put("/usage-limits", response_model=UsageLimitsResponse)
def update_usage_limits(
    payload: UsageLimitsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    settings_repository: UsageSettingsRepository = Depends(
        get_usage_settings_repository
    ),
) -> UsageLimitsResponse:
    """D3: limites por minuto e por dia; 0 desliga a janela."""
    try:
        result = UpdateUsageLimitsUseCase(
            settings_repository=settings_repository,
            access_control=access_control,
        ).execute(
            UpdateUsageLimitsInput(
                user=user,
                per_minute=payload.per_minute,
                per_day=payload.per_day,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _limits(result)


def _limits(result: UsageLimitsDTO) -> UsageLimitsResponse:
    return UsageLimitsResponse(
        per_minute=result.per_minute,
        per_day=result.per_day,
        source=result.source,
    )


def _usage_summary(item: UsageSummaryDTO) -> UsageSummaryResponse:
    return UsageSummaryResponse(
        key=item.key,
        questions=item.questions,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        estimated_cost=item.estimated_cost,
        user_id=item.user_id,
        assistant_id=item.assistant_id,
        last_used_at=item.last_used_at,
        user_name=item.user_name,
    )


@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    assistant_id: str | None = Query(default=None),
    occurred_from: datetime | None = Query(default=None, alias="from"),
    occurred_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    audit_log_repository: AuditLogRepository = Depends(get_audit_log_repository),
) -> list[AuditEventResponse]:
    """UC-13. A trilha so e lida: nao ha rota de alteracao nem de exclusao."""
    use_case = ListAuditEventsUseCase(
        audit_log_repository=audit_log_repository,
        access_control=access_control,
    )
    try:
        events = use_case.execute(
            ListAuditEventsInput(
                user=user,
                user_id=user_id,
                action=action,
                assistant_id=assistant_id,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                limit=limit,
                offset=offset,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return [
        AuditEventResponse(
            id=event.id,
            occurred_at=event.occurred_at,
            user_id=event.user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            details=event.details,
        )
        for event in events
    ]
