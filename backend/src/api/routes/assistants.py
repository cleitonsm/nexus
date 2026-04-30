from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_assistant_repository
from src.api.schemas import AssistantResponse, CreateAssistantRequest
from src.application.use_cases import (
    CreateAssistantInput,
    CreateAssistantUseCase,
    ListAssistantsUseCase,
)
from src.domain import DomainValidationError
from src.infrastructure.database import PostgresAssistantRepository

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
def create_assistant(
    payload: CreateAssistantRequest,
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> AssistantResponse:
    use_case = CreateAssistantUseCase(repository=repository)
    try:
        created = use_case.execute(
            CreateAssistantInput(
                name=payload.name,
                description=payload.description,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return AssistantResponse(
        id=created.id,
        name=created.name,
        description=created.description,
        created_at=created.created_at,
    )


@router.get("", response_model=list[AssistantResponse])
def list_assistants(
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> list[AssistantResponse]:
    use_case = ListAssistantsUseCase(repository=repository)
    assistants = use_case.execute()
    return [
        AssistantResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            created_at=item.created_at,
        )
        for item in assistants
    ]
