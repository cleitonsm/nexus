---
name: new-migration
description: Cria a próxima migração Alembic numerada do Nexus e sincroniza o model SQLAlchemy.
disable-model-invocation: true
argument-hint: <descricao_em_snake_case> [o que muda no esquema]
---

# Nova migração Alembic (ADR 0011)

Argumentos: `$ARGUMENTS` — o primeiro termo é o sufixo em snake_case (ex.: `feedback_tags`); o resto descreve a mudança.

1. Liste `backend/src/infrastructure/database/alembic/versions/`. O próximo número é o maior prefixo + 1, com 4 dígitos. O `down_revision` é o id completo da última revisão (ex.: `0007_reindex_in_worker`). Se houver duas cabeças, pare e avise.
2. Crie `NNNN_<sufixo>.py` (arquivo novo; migração existente nunca é editada) seguindo o padrão das anteriores:
   - docstring em português explicando o motivo, a SPEC/decisão de origem, `Revision ID: NNNN_<sufixo>` e `Revises: <anterior>`;
   - `from __future__ import annotations`, `import sqlalchemy as sa`, `from alembic import op`;
   - `revision = "NNNN_<sufixo>"`, `down_revision`, `branch_labels = None`, `depends_on = None`;
   - `upgrade()` e `downgrade()` completos e simétricos. Coluna nova `NOT NULL` em tabela com dados precisa de `server_default`.
3. Atualize `backend/src/infrastructure/database/models.py` para refletir o mesmo esquema, e os repositórios/mapeamentos afetados.
4. Se a mudança cria tabela ou coluna de domínio, confirme que a entidade ou o DTO correspondente existe e que a SPEC descreve a mudança.
5. Valide: `cd backend && ruff check --select F,E9 src && python -m unittest discover -s tests/unit`.
6. Informe o arquivo criado e lembre que a API aplica as migrações na subida (`docker compose up -d --build backend worker`).
