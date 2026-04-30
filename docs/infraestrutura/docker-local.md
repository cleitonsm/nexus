# Docker Local

## Objetivo

Executar o ciclo completo do MVP (frontend, backend, banco relacional e vector store) com um unico comando e sem dependencias locais de linguagem.

## Pré-requisitos

- Docker Desktop ou Docker Engine compativel com Compose v2.
- Arquivo `.env` criado a partir de `.env.example`.

## Serviços do Compose

- `frontend`: aplicacao Angular (porta `4200`).
- `backend`: API FastAPI (porta `8000`).
- `postgres`: persistencia relacional (porta `5432`).
- `qdrant`: vector store para embeddings (porta `6333`).

## Fluxo de Execução

1. Copiar variaveis:
   - `cp .env.example .env` (Linux/macOS) ou `copy .env.example .env` (Windows).
2. Subir stack:
   - `docker compose up --build`.
3. Validar servicos:
   - `http://localhost:8000/health`;
   - `http://localhost:6333`.

## Comandos Operacionais Úteis

- Subir em background: `docker compose up -d --build`.
- Ver logs: `docker compose logs -f backend`.
- Ver status: `docker compose ps`.
- Parar sem remover dados: `docker compose down`.
- Parar e resetar dados persistidos: `docker compose down -v`.

## Persistência

- `postgres_data`: preserva dados relacionais.
- `qdrant_data`: preserva collections e vetores.
- `backend_cache` (quando habilitado): evita baixar modelo de embedding a cada inicializacao.

## Healthchecks Esperados

- Backend em estado `healthy` apos responder no endpoint `/health`.
- PostgreSQL apto a aceitar conexoes internas no servico `postgres`.
- Qdrant respondendo na API HTTP da porta `6333`.
