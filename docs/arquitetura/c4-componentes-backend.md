# C4 - Componentes do Backend

## Objetivo

Explicitar os componentes internos do backend e as dependências entre camadas.

## Diagrama de Componentes do Backend (C4 Nível 3)

```mermaid
flowchart LR
    Routes["FastAPI Routes"] --> Schemas["API Schemas (Request/Response)"]
    Schemas --> UseCases["Application Use Cases"]

    UseCases --> Domain["Domain (Entities, VOs, Ports)"]
    UseCases --> LangGraph["LangGraph Flow (Retriever, Avaliacao, Geracao, Fallback)"]
    UseCases --> RepoPort["Ports de Repositorio"]
    UseCases --> VectorPort["Port de Vector Store"]
    UseCases --> EmbPort["Port de Embedding"]
    UseCases --> LlmPort["Port de LLM"]

    RepoPort --> PgAdapter["PostgreSQL Adapter"]
    VectorPort --> QdrantAdapter["Qdrant Adapter"]
    EmbPort --> EmbAdapter["Embedding Local Adapter"]
    LlmPort --> LlmAdapter["LLM Adapter"]

    PgAdapter --> PG[("PostgreSQL")]
    QdrantAdapter --> QD[("Qdrant")]
    EmbAdapter --> LocalModel["Modelo de Embedding Local"]
    LlmAdapter --> Provider["Provedor de LLM"]
```

## Notas de Arquitetura

- `domain` e `application` não conhecem FastAPI, Qdrant, PostgreSQL ou SDKs externos.
- `infrastructure` implementa adapters concretos para as portas definidas no domínio/aplicação.
- O fluxo LangGraph permanece na infraestrutura e é invocado por contratos da aplicação.
- O isolamento de conhecimento acontece pela estratégia de collection por assistente no Qdrant.
