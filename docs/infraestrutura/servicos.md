# Serviços

## Backend

API FastAPI responsável por expor casos de uso do Nexus e integrar persistência, RAG e LLM.

## Frontend

Aplicação Angular para criação de assistentes, upload de documentos e chat.

## PostgreSQL

Banco relacional para assistentes, documentos, conversas e mensagens.

## Qdrant

Vector store para chunks vetorizados. No MVP, cada assistente possui uma collection própria.

## LLM Provider

Adapter configurável para geração de respostas. A arquitetura deve permitir trocar provider sem
alterar casos de uso.

## Embedding Local

Componente responsável por transformar chunks em vetores usando modelo executado localmente.

## Avaliação de Qualidade (Fase 1)

Não é um serviço: é um comando executado sob demanda no container do backend
(`python -m src.cli.evaluate`, acionado por `scripts/eval.sh` ou `scripts/eval.ps1`). Usa o
PostgreSQL, o Qdrant e, quando há chave configurada, o provedor de LLM.

## Evolução RAG Enterprise (Planejado)

Os serviços abaixo fazem parte da evolução especificada e **ainda não existem** no `compose.yaml`.

### Keycloak

**Já existe no `compose.yaml` desde a Fase 4** (serviços `keycloak` e `keycloak-db-init`, porta
`8080`). Provedor de identidade. Autentica os usuários e informa papéis e grupos nos tokens. Usa
um banco próprio dentro do PostgreSQL existente e importa o realm de desenvolvimento na subida
(ADR 0008). Usuários de exemplo e console em `infra/keycloak/README.md`.

### Worker de Ingestão

Processo em segundo plano com a mesma imagem do backend. Extrai texto, aplica OCR, fragmenta,
vetoriza e indexa os documentos enfileirados (ADR 0009).

### Fila de Ingestão

Tabela no PostgreSQL existente; não há broker dedicado.

### Armazenamento de Documentos Originais

Volume que guarda os arquivos enviados, para reprocessamento e reindexação.

### Embedding Local, BM25 e Reranker

Modelos executados dentro do backend e do worker, em CPU, com cache em volume. Substituem o
embedding por hash, ainda em uso (ADR 0006 e ADR 0007).

### Observabilidade (perfil opcional)

Coletor e visualização de rastreamentos e métricas, ativados apenas quando necessário (ADR 0010).
