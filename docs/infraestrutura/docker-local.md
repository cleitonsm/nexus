# Docker Local

## Objetivo

Executar todos os componentes do MVP com um comando único, sem instalar dependências de
linguagem na máquina host.

## Serviços Planejados

- `backend`: API FastAPI.
- `frontend`: aplicação Angular.
- `postgres`: persistência relacional.
- `qdrant`: vector store para embeddings.

## Comando Previsto

```bash
docker compose up --build
```

## Volumes

- Volume do PostgreSQL para preservar assistentes e histórico.
- Volume do Qdrant para preservar collections e embeddings.

## Healthchecks

O compose deve validar pelo menos:

- API respondendo em endpoint de saúde.
- PostgreSQL aceitando conexões.
- Qdrant respondendo na API HTTP.
