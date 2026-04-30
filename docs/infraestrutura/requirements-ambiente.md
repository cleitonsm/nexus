# Requisitos de Ambiente

## Dependências Locais

- Git.
- Docker com suporte a Docker Compose.

Não deve ser necessário instalar Python, Node.js, Angular CLI, PostgreSQL ou Qdrant diretamente
na máquina host para executar o MVP.

## Portas Previstas

- `4200`: frontend Angular.
- `8000`: backend FastAPI.
- `5432`: PostgreSQL.
- `6333`: Qdrant HTTP API.

## Variáveis

As variáveis devem ser documentadas em `.env.example` e carregadas pelos containers. Segredos
reais não devem ser versionados.
