class DomainValidationError(ValueError):
    """Raised when domain invariants are violated."""


class IndexOutdatedError(Exception):
    """A base do assistente precisa ser reindexada antes de receber documentos."""


class ReindexInProgressError(Exception):
    """Ja existe uma reindexacao em curso para o assistente."""
