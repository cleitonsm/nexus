# ADR 0002: Clean Architecture com FastAPI

## Status

Aceita.

## Contexto

O backend precisa integrar API HTTP, banco relacional, vector store, embeddings, LLM e fluxo
conversacional. Sem separação de responsabilidades, testes e trocas de implementação ficam
caros rapidamente.

## Decisão

Usar FastAPI na camada de API e organizar o backend em `domain`, `application`,
`infrastructure` e `api`.

## Consequências

- Casos de uso devem depender de interfaces do domínio ou da aplicação.
- Adapters de PostgreSQL, Qdrant, LangGraph e LLM ficam na infraestrutura.
- Testes unitários podem cobrir regras sem subir serviços externos.
- A API deve traduzir HTTP para casos de uso, sem concentrar regra de negócio.
