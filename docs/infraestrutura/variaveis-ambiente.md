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
- `NEXUS_SECRETS_KEY`: chave-mestra usada para criptografar segredos persistidos (ex.: API key global).
- `LLM_API_URL`: endpoint HTTP do provedor de LLM (padrao: API compatível com OpenAI `/chat/completions`).

## Frontend

- `API_BASE_URL`: base URL publicada para o navegador acessar a API.

## Observações Operacionais

- Mudanca em `EMBEDDING_MODEL_NAME` exige compatibilizar dimensao dos vetores no Qdrant.
- Sempre que o modelo de embedding for trocado, executar rotina explicita de reindexacao.
- A variavel `NEXUS_SECRETS_KEY` deve ser estavel por ambiente; trocar sem recriptografar invalida segredos existentes.

## Evolução RAG Enterprise

As variáveis das Fases 1, 2, 3 e 4 já estão no `.env.example`. As demais são previstas nas
especificações, **ainda não estão no `.env.example`** e terão seus valores padrão definidos na
implementação de cada fase.

### Recuperação Semântica (Fase 2, já no `.env.example`)

- `EMBEDDING_MODEL_NAME`: modelo local carregado pelo `sentence-transformers` (ADR 0004).
- `EMBEDDING_VECTOR_SIZE`: dimensão esperada; a API recusa um modelo com dimensão diferente.
- `CHUNK_MAX_TOKENS`: tamanho máximo do chunk. Vazio significa o limite de sequência do modelo
  carregado; um valor acima desse limite é recusado.
- `CHUNK_OVERLAP_SENTENCES`: frases de sobreposição entre chunks consecutivos (padrão `1`).
- `CHUNK_PREFIX_MAX_TOKENS`: teto do prefixo de seção em cada chunk (padrão `32`). Caminhos de
  títulos maiores perdem os títulos mais externos no prefixo.
- `UPLOAD_MAX_BYTES`: tamanho máximo de upload (padrão 20 MB).
- `DOCUMENTS_STORAGE_PATH`: diretório dos arquivos originais, no volume `documents_data`.
- `HF_HOME`: cache dos modelos locais, no volume `backend_cache`.
- `HF_HUB_OFFLINE`: com `1`, nenhum download é tentado; o modelo precisa estar no cache.

Trocar `EMBEDDING_MODEL_NAME` ou os parâmetros de chunking deixa as bases desatualizadas: novos
uploads são recusados até `POST /assistants/{id}/reindex` (RN-16).

### Recuperação (Fase 3, já no `.env.example`)

- `RERANKER_MODEL_NAME`: modelo local de reranking (padrão
  `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`), no mesmo cache de `HF_HOME`.
- `RETRIEVAL_CANDIDATES`: candidatos recuperados pela busca híbrida antes do reranking (padrão `30`).
- `RERANK_TOP_N`: trechos mantidos após o reranking (padrão `5`).
- `RELEVANCE_MIN_SCORE`: nota mínima, de 0 a 1, para um trecho compor o contexto (padrão `0.5`).
  Sem trecho acima dela, a resposta é o fallback, sem chamada ao LLM de geração.
- `CONTEXT_TOKEN_BUDGET` e `HISTORY_TOKEN_BUDGET`: orçamentos de tokens enviados ao LLM (padrões
  `2000` e `1500`), medidos com o tokenizador do modelo de embedding, por aproximação.

- `BM25_K1`, `BM25_B` e `BM25_AVG_LENGTH`: parâmetros do BM25 da busca híbrida (padrões `1.2`,
  `0.75` e `64` termos). **Mudar qualquer um deles exige reindexar os assistentes**: os vetores
  esparsos já gravados não são recalculados. A diferença é detectada (decisão PC-D2): cada
  collection registra os parâmetros com que foi gerada (tabela `app_settings`, chave
  `bm25:<collection>`; as anteriores ao registro assumem os padrões), e a divergência aparece como
  "Reindexação necessária" no painel "Índice de busca" da tela de assistentes, no log
  `index.sparse_parameters_changed` (na subida da API e a cada consulta do estado do índice) e na
  métrica `nexus_index_sparse_parameters_changed_total`. Nada é bloqueado: a busca e os envios
  continuam até a reindexação.

Os valores são pontos de partida, a calibrar com o conjunto de referência (CT-22). As bases
indexadas antes da Fase 3 não têm o vetor esparso: até `POST /assistants/{id}/reindex`, o upload
é recusado (409) e o chat do assistente funciona apenas com a busca densa.

### Autenticação (Fase 4, já no `.env.example`)

- `KEYCLOAK_URL`: endereço do Keycloak visto pelo navegador (`http://localhost:8080`). É o
  emissor conferido em cada token e o endereço que o frontend usa no login.
- `KEYCLOAK_INTERNAL_URL`: endereço pelo qual a API busca as chaves públicas, dentro da rede do
  Compose (`http://keycloak:8080`). Vazio, vale `KEYCLOAK_URL`.
- `KEYCLOAK_PORT`: porta publicada do Keycloak; se mudar, `KEYCLOAK_URL` muda junto.
- `KEYCLOAK_REALM`: realm utilizado (`nexus`).
- `OIDC_AUDIENCE`: audiência esperada no token de acesso (`nexus-api`).
- `OIDC_FRONTEND_CLIENT_ID`: cliente público usado pelo frontend (`nexus-frontend`).
- `KEYCLOAK_ADMIN` e `KEYCLOAK_ADMIN_PASSWORD`: credenciais administrativas do Keycloak (segredo;
  os valores do `.env.example` servem apenas ao ambiente local).
- `NEXUS_FRONTEND_URL`: endereço do frontend visto pelo navegador (`http://localhost:4200`).
  O Compose o repassa ao Keycloak, que o usa no realm importado (redirecionamento, origens e
  logout do cliente `nexus-frontend`). Só vale na primeira importação do realm.
- `CORS_ALLOWED_ORIGINS`: origens autorizadas a chamar a API, separadas por vírgula; `*` é ignorado.
  Deve incluir `NEXUS_FRONTEND_URL`.
- `APP_ENV`: com `local`, a API publica a documentação interativa (`/docs`), que não exige token.
- `AUDIT_RETENTION_DAYS`: retenção da trilha de auditoria em dias (padrão `365`). Só tem efeito
  quando o operador executa `python -m src.cli.purge_audit`; a API nunca apaga eventos.

### Ingestão (Fase 5)

- `INGESTION_MAX_ATTEMPTS`: tentativas antes do estado "falhou".
- `INGESTION_JOB_TIMEOUT_SECONDS`: tempo após o qual um job reservado volta à fila.
- `OCR_LANGUAGES`: idiomas do OCR.

### Avaliação e Logs (Fase 1, já no `.env.example`)

- `LOG_LEVEL`: nível dos logs estruturados em JSON (padrão `INFO`).
- `EVAL_REGRESSION_TOLERANCE`: queda máxima aceita em uma métrica entre duas avaliações (padrão `0.02`).

### Operação (Fase 6, no `.env.example`)

- `RATE_LIMIT_PER_MINUTE` (padrão `20`) e `RATE_LIMIT_PER_DAY` (padrão `500`): perguntas por
  usuário em janelas deslizantes de 60 s e de 24 h (SPEC-006 D3/D6). São os valores padrão: o
  administrador os substitui na tela **Consumo e limites**, e o valor gravado lá prevalece.
  `0` desliga a janela. Substituem `RATE_LIMIT_QUESTIONS`/`RATE_LIMIT_WINDOW_SECONDS` da spec,
  porque a decisão D3 pede duas janelas.
- `LLM_PRICE_INPUT_PER_1K` (`0.00015`), `LLM_PRICE_OUTPUT_PER_1K` (`0.0006`) e
  `LLM_PRICE_CURRENCY` (`USD`): tabela do `gpt-4o-mini` para a estimativa de custo (D7). Ajuste ao
  trocar de modelo; o custo exibido é estimativa, não fatura.
- `OTEL_EXPORTER_OTLP_ENDPOINT` (vazio por padrão) e `OTEL_SERVICE_NAME` (`nexus-backend`):
  exportação de rastreamentos por OTLP/HTTP JSON. Com o perfil `observabilidade`, use
  `http://jaeger:4318`. Vazio, os trechos só alimentam as métricas de `/metrics`.
- `JAEGER_UI_PORT` (`16686`), `PROMETHEUS_PORT` (`9090`), `GRAFANA_PORT` (`3000`),
  `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` (`admin`/`admin`, só desenvolvimento).
- `BACKUP_PATH` (`./backups`), `BACKUP_RETENTION_DAYS` (`7`) e `BACKUP_INTERVAL_SECONDS`
  (`86400`): pasta dos backups no computador, retenção e intervalo do serviço `backup` (D5/D9).

### Observações

- Segredos novos (credenciais do Keycloak) seguem a convenção existente: apenas no `.env` local ou
  em secret manager.
- Parâmetros de recuperação não devem ser alterados sem nova avaliação registrada (RN-14).
