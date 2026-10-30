from datetime import datetime


class DomainValidationError(ValueError):
    """Raised when domain invariants are violated."""


class UnreadableDocumentError(ValueError):
    """O arquivo nao pode ser lido; repetir nao resolve (C1)."""


class TransientServiceError(RuntimeError):
    """Falha passageira de um servico ou ferramenta; vale tentar de novo."""


class IndexOutdatedError(Exception):
    """A base do assistente precisa ser reindexada antes de ser usada."""


class JobOwnershipLostError(Exception):
    """Outro worker assumiu o job: a reserva deste expirou (SPEC-007 fix-3)."""


class ReindexInProgressError(Exception):
    """Ja existe uma reindexacao em curso para o assistente."""


class AuthenticationError(Exception):
    """O token de acesso esta ausente, e invalido ou expirou (RNF-22)."""


class AccessDeniedError(Exception):
    """O usuario autenticado nao tem permissao para a operacao (RN-21)."""


class InvalidDocumentStateError(Exception):
    """A operacao nao e permitida no estado atual do documento (SPEC-005)."""


class DuplicateDocumentError(Exception):
    """RN-26: o assistente ja tem um documento com o mesmo conteudo."""

    def __init__(
        self,
        message: str,
        *,
        existing_document_id: str,
        existing_source_name: str = "",
    ) -> None:
        super().__init__(message)
        self.existing_document_id = existing_document_id
        self.existing_source_name = existing_source_name


class IngestionInProgressError(Exception):
    """Ha documentos do assistente sendo processados pelo worker."""


class GroupDirectoryUnavailableError(Exception):
    """A lista de grupos do provedor de identidade nao pode ser lida (PC-D6)."""


class InvalidFeedbackStateError(Exception):
    """A avaliacao ja foi revisada ou nao admite a operacao (RN-33)."""


class UsageLimitExceededError(Exception):
    """RN-32: o usuario atingiu o limite de perguntas da janela."""

    def __init__(
        self, message: str, *, window: str, limit: int, retry_at: datetime
    ) -> None:
        super().__init__(message)
        self.window = window
        self.limit = limit
        self.retry_at = retry_at


class LLMCredentialInUseError(Exception):
    """RN-38: credencial padrao, credencial escolhida ou modelo em uso."""

    def __init__(
        self,
        message: str,
        *,
        assistant_ids: tuple[str, ...] = (),
        is_default: bool = False,
        models: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.assistant_ids = assistant_ids
        self.is_default = is_default
        self.models = models


class ConcurrentChangeError(Exception):
    """Outra alteracao simultanea venceu; repetir com o estado atual resolve."""


class SystemAssistantReadonlyError(Exception):
    """SPEC-018 (RN-55): o assistente de sistema nao admite a operacao."""


class NotSummarizerConversationError(Exception):
    """SPEC-018 (RN-58): documento pessoal so na conversa do resumidor."""


class ConversationDocumentExistsError(Exception):
    """SPEC-018 (RN-58, D8): a conversa ja tem um documento."""


class SummaryDailyLimitError(Exception):
    """SPEC-018 (RN-60, D20): cota diaria de documentos atingida."""

    def __init__(self, message: str, *, limit: int, retry_at: datetime) -> None:
        super().__init__(message)
        self.limit = limit
        self.retry_at = retry_at


class DocumentTooLongError(Exception):
    """SPEC-018 (RN-60, D15): o texto passa do teto de tokens."""

    def __init__(self, message: str, *, tokens: int, limit: int) -> None:
        super().__init__(message)
        self.tokens = tokens
        self.limit = limit


class SummaryNotReadyError(Exception):
    """SPEC-018: o resumo ainda nao esta pronto (409 summary_not_ready)."""


class SummaryNotFailedError(Exception):
    """SPEC-018 (RN-64): so o resumo que falhou pode ser refeito."""
