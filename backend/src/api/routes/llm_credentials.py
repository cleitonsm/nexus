"""Rotas da SPEC-013: credenciais de LLM (RF-87 a RF-89) e opcoes para o assistente.

As rotas so traduzem HTTP: permissao, regras e auditoria ficam nos casos de
uso. A chave entra pelo corpo e nunca volta (RN-39).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.dependencies import (
    LLMTestGatewayFactory,
    get_access_control,
    get_assistant_repository,
    get_current_user,
    get_llm_credential_repository,
    get_llm_insecure_http_allowed,
    get_llm_test_gateway_factory,
    get_secret_cipher,
    get_usage_settings,
)
from src.api.schemas.llm_credentials import (
    CreateLLMCredentialRequest,
    DefaultChangeImpactRequest,
    DefaultChangeImpactResponse,
    LLMCredentialListResponse,
    LLMCredentialOptionResponse,
    LLMCredentialResponse,
    LLMCredentialTestResponse,
    LLMModelPayload,
    LLMModelResponse,
    TestLLMCredentialRequest,
    UpdateLLMCredentialRequest,
)
from src.application.services import AccessControl, UsageSettings
from src.application.use_cases import (
    CreateLLMCredentialInput,
    CreateLLMCredentialUseCase,
    DefaultChangeImpactInput,
    DeleteLLMCredentialUseCase,
    GetDefaultChangeImpactUseCase,
    LLMCredentialDTO,
    LLMCredentialKeyMissingError,
    LLMCredentialKeyUnreadableError,
    LLMCredentialNotFoundError,
    LLMCredentialRefInput,
    ListLLMCredentialOptionsUseCase,
    ListLLMCredentialsUseCase,
    LLMModelInput,
    SetDefaultLLMCredentialUseCase,
    TestLLMCredentialInput,
    TestLLMCredentialUseCase,
    UpdateLLMCredentialInput,
    UpdateLLMCredentialUseCase,
)
from src.domain import (
    PROVIDER_ENDPOINTS,
    AssistantRepository,
    AuthenticatedUser,
    DomainValidationError,
    LLMCredentialRepository,
    SecretCipher,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/llm-credentials",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],
)
options_router = APIRouter(
    prefix="/llm-credentials",
    tags=["assistants"],
    dependencies=[Depends(get_current_user)],
)


class _Deps:
    """Dependencias comuns, resolvidas uma vez por requisicao."""

    def __init__(
        self,
        user: AuthenticatedUser = Depends(get_current_user),
        access_control: AccessControl = Depends(get_access_control),
        credentials: LLMCredentialRepository = Depends(get_llm_credential_repository),
        assistants: AssistantRepository = Depends(get_assistant_repository),
    ) -> None:
        self.user = user
        self.common = {
            "credentials": credentials,
            "assistants": assistants,
            "access_control": access_control,
        }


@router.get("", response_model=LLMCredentialListResponse)
def list_llm_credentials(
    deps: _Deps = Depends(),
    settings: UsageSettings = Depends(get_usage_settings),
) -> LLMCredentialListResponse:
    items = ListLLMCredentialsUseCase(**deps.common).execute(deps.user)
    return LLMCredentialListResponse(
        items=[_credential(item) for item in items],
        provider_urls={provider.value: url for provider, url in PROVIDER_ENDPOINTS.items()},
        currency=settings.pricing.currency,
    )


@router.post("", response_model=LLMCredentialResponse, status_code=status.HTTP_201_CREATED)
def create_llm_credential(
    payload: CreateLLMCredentialRequest,
    deps: _Deps = Depends(),
    cipher: SecretCipher = Depends(get_secret_cipher),
    allow_insecure_http: bool = Depends(get_llm_insecure_http_allowed),
) -> LLMCredentialResponse:
    use_case = CreateLLMCredentialUseCase(
        **deps.common, cipher=cipher, allow_insecure_http=allow_insecure_http
    )
    with _translated():
        created = use_case.execute(
            CreateLLMCredentialInput(
                user=deps.user,
                name=payload.name,
                provider=payload.provider,
                api_url=payload.api_url,
                models=_models(payload.models),
                default_model=payload.default_model,
                api_key=payload.api_key,
                make_default=payload.make_default,
            )
        )
    return _credential(created)


@router.put("/{credential_id}", response_model=LLMCredentialResponse)
def update_llm_credential(
    credential_id: str,
    payload: UpdateLLMCredentialRequest,
    deps: _Deps = Depends(),
    cipher: SecretCipher = Depends(get_secret_cipher),
    allow_insecure_http: bool = Depends(get_llm_insecure_http_allowed),
) -> LLMCredentialResponse:
    use_case = UpdateLLMCredentialUseCase(
        **deps.common, cipher=cipher, allow_insecure_http=allow_insecure_http
    )
    with _translated():
        updated = use_case.execute(
            UpdateLLMCredentialInput(
                user=deps.user,
                credential_id=credential_id,
                name=payload.name,
                provider=payload.provider,
                api_url=payload.api_url,
                models=_models(payload.models),
                default_model=payload.default_model,
                api_key=payload.api_key,
            )
        )
    return _credential(updated)


@router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_llm_credential(credential_id: str, deps: _Deps = Depends()) -> Response:
    with _translated():
        DeleteLLMCredentialUseCase(**deps.common).execute(
            LLMCredentialRefInput(user=deps.user, credential_id=credential_id)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{credential_id}/default", response_model=LLMCredentialResponse)
def set_default_llm_credential(
    credential_id: str, deps: _Deps = Depends()
) -> LLMCredentialResponse:
    with _translated():
        result = SetDefaultLLMCredentialUseCase(**deps.common).execute(
            LLMCredentialRefInput(user=deps.user, credential_id=credential_id)
        )
    return _credential(result)


@router.post("/{credential_id}/impact", response_model=DefaultChangeImpactResponse)
def default_change_impact(
    credential_id: str,
    payload: DefaultChangeImpactRequest,
    deps: _Deps = Depends(),
) -> DefaultChangeImpactResponse:
    """D11: quem segue a padrao e quem recua, antes de confirmar a troca."""
    with _translated():
        impact = GetDefaultChangeImpactUseCase(**deps.common).execute(
            DefaultChangeImpactInput(
                user=deps.user,
                credential_id=credential_id,
                model_names=(
                    tuple(payload.model_names) if payload.model_names is not None else None
                ),
            )
        )
    return DefaultChangeImpactResponse(
        credential_id=impact.credential_id,
        following_assistant_ids=list(impact.following_assistant_ids),
        falling_back_assistant_ids=list(impact.falling_back_assistant_ids),
    )


@router.post("/{credential_id}/test", response_model=LLMCredentialTestResponse)
def test_llm_credential(
    credential_id: str,
    payload: TestLLMCredentialRequest,
    deps: _Deps = Depends(),
    cipher: SecretCipher = Depends(get_secret_cipher),
    gateway_factory: LLMTestGatewayFactory = Depends(get_llm_test_gateway_factory),
) -> LLMCredentialTestResponse:
    use_case = TestLLMCredentialUseCase(
        **deps.common, cipher=cipher, gateway_factory=gateway_factory
    )
    with _translated():
        try:
            result = use_case.execute(
                TestLLMCredentialInput(
                    user=deps.user, credential_id=credential_id, model=payload.model
                )
            )
        except LLMCredentialKeyMissingError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "llm_credential_key_missing",
                    "message": "A credencial não tem chave gravada.",
                },
            ) from exc
        except LLMCredentialKeyUnreadableError as exc:
            # Erro do servidor (chave mestra trocada), nao do provedor.
            logger.error(
                "admin.llm_credential_test.decrypt_failed",
                extra={"credential_id": credential_id},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "llm_credential_key_unreadable",
                    "message": (
                        "A chave gravada não pôde ser decifrada. A NEXUS_SECRETS_KEY "
                        "mudou? Grave a chave de novo."
                    ),
                },
            ) from exc
        except DomainValidationError:
            raise
        except (RuntimeError, ValueError) as exc:
            # Nao repete o texto do provedor, que pode ecoar a requisicao (fix-14).
            logger.warning(
                "admin.llm_credential_test.failed",
                extra={"credential_id": credential_id, "error_type": type(exc).__name__},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Falha na comunicação com o LLM.",
            ) from exc
    return LLMCredentialTestResponse(
        ok=result.ok,
        credential_id=result.credential_id,
        model=result.model,
        message="Comunicação com o LLM validada com a chave desta credencial.",
        response_preview=result.response_preview,
    )


@options_router.get("/options", response_model=list[LLMCredentialOptionResponse])
def list_llm_credential_options(deps: _Deps = Depends()) -> list[LLMCredentialOptionResponse]:
    """Opcoes do formulario do assistente (D7: so o administrador escolhe)."""
    return [
        LLMCredentialOptionResponse(
            id=item.id,
            name=item.name,
            provider=item.provider,
            models=list(item.models),
            default_model=item.default_model,
            is_default=item.is_default,
        )
        for item in ListLLMCredentialOptionsUseCase(**deps.common).execute(deps.user)
    ]


class _translated:
    """Erros de dominio e de caso de uso viram status HTTP."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None or isinstance(exc, HTTPException):
            return False
        if isinstance(exc, LLMCredentialNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "llm_credential_not_found", "message": "credential not found"},
            ) from exc
        if isinstance(exc, DomainValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        # LLMCredentialInUseError e ConcurrentChangeError: tratados em errors.py (409).
        return False


def _models(models: list[LLMModelPayload]) -> tuple[LLMModelInput, ...]:
    return tuple(
        LLMModelInput(
            name=item.name,
            input_per_1k=item.input_per_1k,
            output_per_1k=item.output_per_1k,
        )
        for item in models
    )


def _credential(item: LLMCredentialDTO) -> LLMCredentialResponse:
    return LLMCredentialResponse(
        id=item.id,
        name=item.name,
        provider=item.provider,
        api_url=item.api_url,
        models=[
            LLMModelResponse(
                name=model.name,
                input_per_1k=model.input_per_1k,
                output_per_1k=model.output_per_1k,
            )
            for model in item.models
        ],
        default_model=item.default_model,
        is_default=item.is_default,
        key_configured=item.key_configured,
        assistant_ids=list(item.assistant_ids),
        following_assistant_ids=list(item.following_assistant_ids),
    )
