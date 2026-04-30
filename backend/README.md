# Backend

Futura API FastAPI do Nexus.

## Estrutura Planejada

- `src/domain`: entidades, value objects e interfaces.
- `src/application`: casos de uso, serviços de aplicação e DTOs.
- `src/infrastructure`: adapters de banco, Qdrant, embeddings, LLM e LangGraph.
- `src/api`: rotas, schemas e bootstrap FastAPI.
- `tests/unit`: testes puros de domínio e aplicação.
- `tests/integration`: testes com serviços Docker.

O backend deve seguir a documentação em `docs/arquitetura/clean-architecture-backend.md`.
