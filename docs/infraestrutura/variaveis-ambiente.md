# Variáveis de Ambiente

## Backend

- `APP_ENV`: ambiente de execução.
- `API_HOST`: host da API dentro do container.
- `API_PORT`: porta da API.
- `DATABASE_URL`: conexão PostgreSQL.
- `QDRANT_URL`: URL do Qdrant.
- `EMBEDDING_MODEL_NAME`: modelo local de embeddings.
- `LLM_PROVIDER`: provider de geração de resposta.
- `LLM_MODEL`: modelo usado pelo provider.

## Frontend

- `API_BASE_URL`: URL pública da API para o navegador.

## Segurança

`.env.example` pode conter valores de desenvolvimento. `.env` real não deve ser commitado.
