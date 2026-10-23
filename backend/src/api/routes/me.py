from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import (
    get_access_control,
    get_current_user,
    get_group_directory,
)
from src.api.schemas import CurrentUserResponse
from src.application.services import AccessControl
from src.application.use_cases import (
    DescribeCurrentUserUseCase,
    ListAvailableGroupsUseCase,
)
from src.domain import AuthenticatedUser, GroupDirectory

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


@router.get("/groups", response_model=list[str])
def list_groups(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    directory: GroupDirectory = Depends(get_group_directory),
) -> list[str]:
    """PC-D6: grupos do Keycloak para administrador e curador.

    503 quando o Keycloak nao responde ou o cliente de servico nao esta
    configurado; a tela volta ao campo de texto.
    """
    return ListAvailableGroupsUseCase(directory, access_control).execute(user)
