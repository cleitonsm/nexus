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
   - `http://localhost:4200/health`;
   - Qdrant interno acessivel em `http://qdrant:6333` a partir do container `backend`.

## Validacao MVP ponta a ponta

Fluxo minimo validado para o MVP:

1. Criar assistente.
2. Enviar documento para o assistente.
3. Criar conversa.
4. Enviar pergunta no endpoint de chat.
5. Reiniciar backend.
6. Confirmar que o historico da conversa continua disponivel.

Exemplo de comandos (bash/curl):

```bash
API="http://localhost:8000"

ASSISTANT_ID=$(curl -sS -X POST "$API/assistants" \
  -H "Content-Type: application/json" \
  -d '{"name":"Assistente E2E","description":"Validacao MVP"}' | jq -r '.id')

curl -sS -X POST "$API/assistants/$ASSISTANT_ID/documents" \
  -F "file=@docs/negocio/visao-produto.md;type=text/markdown"

CONVERSATION_ID=$(curl -sS -X POST "$API/conversations" \
  -H "Content-Type: application/json" \
  -d "{\"assistant_id\":\"$ASSISTANT_ID\"}" | jq -r '.id')

curl -sS -X POST "$API/conversations/$CONVERSATION_ID/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"Qual e o objetivo do MVP?","top_k":3}'

docker compose restart backend
curl -sS "$API/conversations/$CONVERSATION_ID"
```

No ambiente local validado neste repositorio:

- `fallback_used=false` para pergunta com contexto.
- `messages_before=2` e `messages_after_restart=2`, confirmando persistencia.

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

## Colisoes de porta no host

Se as portas padrao do host ja estiverem em uso:

- ajuste no `.env` os valores de `POSTGRES_PORT` e `QDRANT_PORT`; ou
- use mapeamento dinamico para nao fixar porta no host:
  - PowerShell: `$env:POSTGRES_PORT='0'; $env:QDRANT_PORT='0'; docker compose up -d --build`
  - bash: `POSTGRES_PORT=0 QDRANT_PORT=0 docker compose up -d --build`

## Healthchecks Esperados

- Backend em estado `healthy` apos responder no endpoint `/health`.
- PostgreSQL apto a aceitar conexoes internas no servico `postgres`.
- Qdrant respondendo na API HTTP da porta `6333`.
