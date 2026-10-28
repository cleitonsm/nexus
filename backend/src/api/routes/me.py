from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import (
    get_access_control,
    get_assistant_repository,
    get_current_user,
    get_group_directory,
    get_home_assistant_repository,
)
from src.api.schemas import (
    CurrentUserResponse,
    HomeAssistantsRequest,
    HomeAssistantsResponse,
)
from src.application.dto import HomeAssistantsDTO
from src.application.services import AccessControl
from src.application.use_cases import (
    DescribeCurrentUserUseCase,
    GetHomeAssistantsUseCase,
    ListAvailableGroupsUseCase,
    SetHomeAssistantsInput,
    SetHomeAssistantsUseCase,
)
from src.domain import (
    AssistantRepository,
    AuthenticatedUser,
    GroupDirectory,
    HomeAssistantPreferenceRepository,
)

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


def _home_response(result: HomeAssistantsDTO) -> HomeAssistantsResponse:
    return HomeAssistantsResponse(
        assistant_ids=list(result.assistant_ids),
        default_assistant_id=result.default_assistant_id,
        max=result.max,
        customized=result.customized,
    )


@router.get("/me/home-assistants", response_model=HomeAssistantsResponse)
def get_home_assistants(
    user: AuthenticatedUser = Depends(get_current_user),
    preferences: HomeAssistantPreferenceRepository = Depends(get_home_assistant_repository),
    assistants: AssistantRepository = Depends(get_assistant_repository),
    access_control: AccessControl = Depends(get_access_control),
) -> HomeAssistantsResponse:
    """SPEC-016 (RN-49): acesso rapido efetivo do usuario do token."""
    result = GetHomeAssistantsUseCase(
        preferences=preferences, assistants=assistants, access_control=access_control
    ).execute(user)
    return _home_response(result)


@router.put("/me/home-assistants", response_model=HomeAssistantsResponse)
def set_home_assistants(
    payload: HomeAssistantsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    preferences: HomeAssistantPreferenceRepository = Depends(get_home_assistant_repository),
    assistants: AssistantRepository = Depends(get_assistant_repository),
    access_control: AccessControl = Depends(get_access_control),
) -> HomeAssistantsResponse:
    """SPEC-016 (RF-103, RF-106): troca a selecao inteira; 422 com o ``code`` da regra."""
    result = SetHomeAssistantsUseCase(
        preferences=preferences, assistants=assistants, access_control=access_control
    ).execute(
        SetHomeAssistantsInput(
            user=user,
            assistant_ids=tuple(payload.assistant_ids),
            default_assistant_id=payload.default_assistant_id,
        )
    )
    return _home_response(result)
