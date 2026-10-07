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

## Evolução RAG Enterprise (Planejado)

A Fase 1, já implementada, não altera os requisitos de ambiente: não acrescenta serviços, portas
nem dependências.

Para as próximas fases, a premissa de dependências locais não muda: Git e Docker continuam sendo
as únicas exigências. O que muda é o consumo de recursos.

### Portas Adicionais Previstas (Host)

- `8080`: Keycloak.
- Portas do perfil opcional de observabilidade, definidas na implementação.

### Volumes Adicionais

- `backend_cache`: passa de opcional a necessário, para os modelos de embedding e de reranking.
- `documents_data`: arquivos originais dos documentos.
- `keycloak` usa o volume `postgres_data`, em banco próprio.

### Capacidade

- A capacidade mínima atual (8 GB para o Docker) deixa de ser suficiente com modelos locais,
  Keycloak e worker ativos.
- Passa a valer como mínimo o que hoje é indicado como confortável: 6 vCPUs, 12 GB de memória para
  o Docker e 30 GB de disco livre.
- Não é exigida GPU; embeddings, reranking e OCR rodam em CPU.
- A primeira construção das imagens e o primeiro uso baixam os modelos e levam mais tempo.

### Checklist Adicional

- Keycloak responde e o realm `nexus` foi importado.
- Login pelo frontend redireciona para o Keycloak e retorna autenticado.
- O worker está em execução e consome a fila.
- O modelo de embedding está no volume de cache e a ingestão funciona sem acesso à internet.
