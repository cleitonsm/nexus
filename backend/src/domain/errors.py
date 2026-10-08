class DomainValidationError(ValueError):
    """Raised when domain invariants are violated."""


class IndexOutdatedError(Exception):
    """A base do assistente precisa ser reindexada antes de ser usada."""


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
