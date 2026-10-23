# Nexus — guia para o Claude Code

Plataforma RAG corporativa: cada assistente responde só com trechos da própria base, filtrados pelos grupos do usuário. Monólito modular (ADR 0001): backend FastAPI em Clean Architecture, worker de ingestão, frontend Angular 19 + NgRx, PostgreSQL 16, Qdrant e Keycloak via `compose.yaml`.

Para implementar qualquer coisa, siga a skill **`desenvolvedor-nexus`** (`.claude/skills/desenvolvedor-nexus/SKILL.md`): arquitetura, tecnologias por camada e limites.

## Comandos

| O quê | Comando |
|---|---|
| Lint (igual ao CI) | `cd backend && ruff check --select F,E9 src tests` |
| Testes unitários backend | `cd backend && python -m unittest discover -s tests/unit` |
| Testes frontend | `cd frontend && npm test` |
| Build frontend | `cd frontend && npm run build` |
| Subir a stack | `docker compose up -d --build` |
| Avaliação do RAG | `scripts/eval.ps1` (PowerShell) ou `scripts/eval.sh` |
| Portão de qualidade local | `scripts/quality-gate.sh [--fidelidade] [conjunto]` |

## Regras que não se negociam

- SDD: mudança de comportamento entra na SPEC (`docs/especificacao/specs/`) antes do código.
- `src/domain` não importa framework, ORM, Qdrant, LangGraph nem SDK de LLM.
- Toda busca no Qdrant filtra `user_groups` e `active`; todo caso de uso de rota consulta a `AccessPolicy`.
- Mudança de esquema = nova migração numerada; migração existente nunca é editada.
- Nunca ler nem gravar `.env`, segredo, token ou documento real. Dados de exemplo são fictícios.

## Automações do projeto

- Hooks (`.claude/settings.json`): `guard.py` bloqueia `.env` e edição de migração existente; `ruff_check.py` roda o ruff do CI após editar `.py`.
- Skills: `/spec-to-code <SPEC>` (fluxo SDD completo) e `/new-migration <nome>`.
- Subagentes: `architecture-guard` (fronteiras e ADRs) e `rag-quality-reviewer` (pipeline RAG).
- MCP (`.mcp.json`): `context7` (documentação atual), `playwright` (navegador), `postgres` (somente leitura no banco local; ver `.claude/mcp/README.md`).
