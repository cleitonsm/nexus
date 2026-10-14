"""Confirmacao de transacoes (fix-7).

Sem ``rollback`` depois de uma falha no ``commit`` a sessao fica inutilizavel
("transaction has been rolled back due to a previous exception"), o que derruba
workers de longa duracao. Todo repositorio confirma por aqui.
"""

from __future__ import annotations

from typing import Protocol


class _CommitSession(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def commit_or_rollback(session: _CommitSession) -> None:
    """Confirma; se falhar, desfaz a transacao e repete o erro original."""
    try:
        session.commit()
    except BaseException:
        session.rollback()
        raise
