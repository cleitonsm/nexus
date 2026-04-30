# Variáveis de Ambiente

## Convenções

- `.env.example` define valores padrao para desenvolvimento local.
- `.env` local sobrescreve os valores e nao deve ser versionado.
- Variaveis de segredo devem existir apenas no `.env` local ou em secret manager.

## Backend (Obrigatórias)

- `APP_ENV`: ambiente de execucao (`local`, `dev`, `prod`).
- `API_HOST`: host de bind da API no container (ex.: `0.0.0.0`).
- `API_PORT`: porta de bind da API (ex.: `8000`).
- `DATABASE_URL`: string de conexao PostgreSQL usada pelo backend.
- `QDRANT_URL`: URL do servico Qdrant no Compose.
- `EMBEDDING_MODEL_NAME`: modelo de embedding local (padrao recomendado: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`).
- `LLM_PROVIDER`: provedor de geracao de resposta.
- `LLM_MODEL`: modelo de geracao de resposta.

## Frontend

- `API_BASE_URL`: base URL publicada para o navegador acessar a API.

## Observações Operacionais

- Mudanca em `EMBEDDING_MODEL_NAME` exige compatibilizar dimensao dos vetores no Qdrant.
- Sempre que o modelo de embedding for trocado, executar rotina explicita de reindexacao.
