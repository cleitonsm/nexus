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
