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

## Evolução RAG Enterprise

A evolução do backend está especificada em `docs/especificacao/specs/`. A Fase 1 está
implementada; as Fases 2 a 6 ainda não.

### Já Implementado (Fase 1)

- Avaliação de qualidade: `EvaluateAssistantUseCase`, `CompareEvaluationReportsUseCase`,
  adaptadores em `src/infrastructure/evaluation` e comando `python -m src.cli.evaluate`.
  Ver `tests/evaluation/README.md`.
- Logs estruturados em JSON com identificador de requisição (`src/infrastructure/observability`
  e `src/api/middleware.py`); o cabeçalho `X-Request-ID` é aceito e devolvido pela API.

### Estado Atual Relevante

- Embeddings: `LocalHashEmbeddingGateway` (hash de palavras); passará a ser apenas dublê de testes.
- Chunking: corte fixo dentro de `IngestDocumentUseCase`.
- Busca: densa, sem nota mínima.
- Esquema do banco: criado por `create_all` na subida da API.
- Rotas sem autenticação.

### Estrutura Prevista (Fases 2 a 6)

- `src/domain`: novas portas (`TokenVerifier`, `DocumentChunker`, `SparseEmbeddingGateway`,
  `RerankerGateway`, `IngestionJobQueue`, `DocumentFileStorage`, `UsageLimiter`),
  `AccessPolicy`, `AuthenticatedUser` e `Citation`.
- `src/application`: casos de uso de reindexação, ciclo de vida de documentos,
  permissões, auditoria, consumo e feedback.
- `src/infrastructure`: `auth`, `chunking`, `queue`, `reranking` e `storage`.
- `src/api`: autenticação em todos os routers, exceto `/health`, e rota de streaming do chat.

### Pontos de Entrada

Além da API, o mesmo código é executado pelo comando de avaliação (`src/cli/evaluate.py`) e, a
partir da Fase 5, pelo worker de ingestão. Ambos invocam casos de uso; nenhum contém regra de negócio.

### Testes

A estratégia e os casos de teste (CT-01 a CT-48) estão em
`docs/especificacao/estrategia-de-testes.md`; CT-01 a CT-03 e CT-05 já têm testes no repositório.
Os testes usam `unittest`. Testes unitários continuam sem Docker, banco,
Qdrant, Keycloak ou LLM real.
