from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import (
    get_configured_llm_model,
    get_secret_cipher,
    get_secret_settings_repository,
)
from src.api.schemas import (
    ApiKeyStatusResponse,
    ApiKeyTestResponse,
    SaveApiKeyRequest,
)
from src.application.use_cases import (
    GetGlobalApiKeyValueUseCase,
    GetGlobalApiKeyStatusUseCase,
    SaveGlobalApiKeyInput,
    SaveGlobalApiKeyUseCase,
)
from src.infrastructure.database import PostgresSecretSettingsRepository
from src.infrastructure.llm import HttpChatCompletionsLLM
from src.infrastructure.secrets import FernetSecretCipher

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/api-key/status", response_model=ApiKeyStatusResponse)
def get_api_key_status(
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
) -> ApiKeyStatusResponse:
    result = GetGlobalApiKeyStatusUseCase(
        secret_repository=secret_repository
    ).execute()
    return ApiKeyStatusResponse(configured=result.configured)


@router.post(
    "/api-key",
    response_model=ApiKeyStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_api_key(
    payload: SaveApiKeyRequest,
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
) -> ApiKeyStatusResponse:
    use_case = SaveGlobalApiKeyUseCase(
        secret_repository=secret_repository,
        secret_cipher=secret_cipher,
    )
    try:
        result = use_case.execute(
            SaveGlobalApiKeyInput(api_key=payload.api_key)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ApiKeyStatusResponse(configured=result.configured)


@router.post("/api-key/test", response_model=ApiKeyTestResponse)
def test_api_key(
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
) -> ApiKeyTestResponse:
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
    try:
        answer = llm_gateway.generate(
            prompt=(
                "Teste de conectividade do Nexus. "
                "Responda apenas: OK"
            ),
            context_chunks=[
                "Validacao administrativa de conectividade com LLM."
            ],
            conversation_history=[],
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ApiKeyTestResponse(
        ok=True,
        model=model,
        message="Comunicacao com a LLM validada usando a API key armazenada.",
        response_preview=answer[:200],
    )
