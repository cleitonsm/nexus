from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import (
    get_secret_cipher,
    get_secret_settings_repository,
)
from src.api.schemas import ApiKeyStatusResponse, SaveApiKeyRequest
from src.application.use_cases import (
    GetGlobalApiKeyStatusUseCase,
    SaveGlobalApiKeyInput,
    SaveGlobalApiKeyUseCase,
)
from src.infrastructure.database import PostgresSecretSettingsRepository
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
        result = use_case.execute(SaveGlobalApiKeyInput(api_key=payload.api_key))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ApiKeyStatusResponse(configured=result.configured)
