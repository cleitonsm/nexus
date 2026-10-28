"""SPEC-016: acesso rapido da tela inicial no PostgreSQL."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.domain import AssistantId, HomeAssistantSelection

from .models import UserHomeAssistantModel
from .transactions import commit_or_rollback


class PostgresHomeAssistantPreferenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, owner_user_id: str) -> HomeAssistantSelection | None:
        rows = self._session.scalars(
            select(UserHomeAssistantModel)
            .where(UserHomeAssistantModel.owner_user_id == owner_user_id)
            .order_by(UserHomeAssistantModel.position)
        ).all()
        if not rows:
            return None
        defaults = [row.assistant_id for row in rows if row.is_default]
        # O indice garante no maximo um padrao; sem nenhum (linha do padrao
        # apagada por cascata), o primeiro assume, como na D8.
        default_id = defaults[0] if defaults else rows[0].assistant_id
        return HomeAssistantSelection(
            assistant_ids=tuple(AssistantId(row.assistant_id) for row in rows),
            default_id=AssistantId(default_id),
        )

    def replace(self, owner_user_id: str, selection: HomeAssistantSelection) -> None:
        """Apaga e insere na mesma transacao: quem le ve a selecao antiga ou a nova."""
        self._session.execute(
            delete(UserHomeAssistantModel).where(
                UserHomeAssistantModel.owner_user_id == owner_user_id
            )
        )
        self._session.add_all(
            UserHomeAssistantModel(
                owner_user_id=owner_user_id,
                assistant_id=assistant_id.value,
                position=position,
                is_default=assistant_id == selection.default_id,
            )
            for position, assistant_id in enumerate(selection.assistant_ids)
        )
        commit_or_rollback(self._session)
