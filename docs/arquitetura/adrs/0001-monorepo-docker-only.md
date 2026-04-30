# ADR 0001: Monorepo e Ambiente Local via Docker

## Status

Aceita.

## Contexto

O projeto possui frontend, backend e serviços de apoio. Para o MVP, manter tudo em um único
repositório reduz coordenação e facilita execução local.

## Decisão

Usar monorepo e exigir Docker como única dependência operacional local além do próprio Git.

## Consequências

- O onboarding deve depender de poucos comandos.
- Backend, frontend, PostgreSQL e Qdrant serão orquestrados por `compose.yaml`.
- Dependências de linguagem devem rodar dentro de containers.
- O repositório deve preservar separação clara entre documentação, backend, frontend e infra.
