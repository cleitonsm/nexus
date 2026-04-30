# Requisitos de Ambiente

## Dependências Locais

- Git.
- Docker com suporte a Docker Compose.

Não deve ser necessário instalar Python, Node.js, Angular CLI, PostgreSQL ou Qdrant diretamente
na máquina host para executar o MVP.

## Premissa de Execução

- O projeto deve subir e executar com `docker compose up --build`.
- Todas as rotinas de desenvolvimento, teste e execução devem ocorrer dentro de containers.
- O host precisa apenas orquestrar o ambiente; não deve compilar, rodar ou testar serviços fora do Docker.

## Portas Previstas

- `4200`: frontend Angular.
- `8000`: backend FastAPI.
- `5432`: PostgreSQL.
- `6333`: Qdrant HTTP API.

## Volumes Persistentes

- `postgres_data`: persistência de dados relacionais (assistentes, documentos, conversas e mensagens).
- `qdrant_data`: persistência das collections vetoriais e índices.
- `backend_cache` (opcional): cache local de modelos/artefatos do backend para reduzir tempo de inicialização.

## Recursos Mínimos Recomendados

- CPU: 4 vCPUs.
- Memória RAM: 8 GB disponíveis para Docker.
- Disco: 20 GB livres para imagens, volumes e modelos locais.

Para execução confortável com ingestão de documentos e embeddings locais em paralelo:

- CPU: 6 vCPUs ou mais.
- Memória RAM: 12 GB ou mais.

## Variáveis

As variáveis devem ser documentadas em `.env.example` e carregadas pelos containers. Segredos
reais não devem ser versionados.
