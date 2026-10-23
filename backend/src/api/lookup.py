"""Assistente inexistente sem virar oraculo de enumeracao (fix-14, RN-24)."""

from __future__ import annotations

from fastapi import HTTPException, status

from src.application.services import AccessControl
from src.domain import AssistantId, AuthenticatedUser


def assistant_not_found(
    user: AuthenticatedUser,
    access_control: AccessControl,
    assistant_id: AssistantId,
    attempted: str,
) -> HTTPException:
    """Quem nao pode usar o assistente recebe 403, exista ele ou nao.

    Assistente sem grupos so admite administradores, entao para os demais o
    inexistente e indistinguivel do proibido; so o administrador chega ao 404.
    """
    access_control.require_assistant_access(user, assistant_id, attempted)
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="assistant not found",
    )
