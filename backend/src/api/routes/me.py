from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import get_access_control, get_current_user
from src.api.schemas import CurrentUserResponse
from src.application.services import AccessControl
from src.application.use_cases import DescribeCurrentUserUseCase
from src.domain import AuthenticatedUser

router = APIRouter(tags=["session"], dependencies=[Depends(get_current_user)])


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
) -> CurrentUserResponse:
    """Identidade, papeis e grupos lidos do token."""
    described = DescribeCurrentUserUseCase(access_control).execute(user)
    return CurrentUserResponse(
        id=described.id,
        name=described.name,
        roles=list(described.roles),
        groups=list(described.groups),
    )
