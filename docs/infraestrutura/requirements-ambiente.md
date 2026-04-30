# Requisitos de Ambiente

## Dependências Locais Obrigatórias

- Git `2.40+`.
- Docker Desktop `4.30+` (Windows/macOS) ou Docker Engine `24+` (Linux).
- Docker Compose v2 (`docker compose`).

Nao deve ser necessario instalar Python, Node.js, Angular CLI, PostgreSQL ou Qdrant no host para executar o MVP.

## Premissa de Execução

- O ambiente sobe com `docker compose up --build`.
- Build, testes, migracoes e execucao dos servicos acontecem dentro de containers.
- O host apenas orquestra o ambiente.

## Portas Previstas (Host)

- `4200`: frontend Angular.
- `8000`: backend FastAPI.
- `5432`: PostgreSQL.
- `6333`: Qdrant HTTP API.

## Volumes Persistentes

- `postgres_data`: dados relacionais (assistentes, documentos, conversas e mensagens).
- `qdrant_data`: collections vetoriais e indices.
- `backend_cache` (opcional): cache de modelos de embedding para reduzir tempo de bootstrap.

## Capacidade Minima Recomendada

- CPU: 4 vCPUs.
- Memoria RAM disponivel ao Docker: 8 GB.
- Disco livre: 20 GB (imagens, volumes e cache de modelos).

## Capacidade Recomendada para Uso Confortavel

- CPU: 6 vCPUs ou mais.
- Memoria RAM disponivel ao Docker: 12 GB ou mais.
- Disco livre: 30 GB ou mais para iteracoes com reindexacao.

## Variáveis e Segredos

- Variaveis obrigatorias e opcionais devem estar documentadas em `.env.example`.
- Segredos reais devem ficar em `.env` local (nao versionado).
- Qualquer alteracao de modelo de embedding deve atualizar:
  - `EMBEDDING_MODEL_NAME`;
  - dimensao da collection no Qdrant;
  - rotina de reindexacao.

## Checklist de Validacao Rápida

- `docker --version` retorna versao compativel.
- `docker compose version` retorna Compose v2.
- `docker compose up --build` sobe frontend, backend, postgres e qdrant.
- Backend responde em `/health`.
- Qdrant responde em `http://localhost:6333`.
