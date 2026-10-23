# Clean Architecture no Backend

## Objetivo

Separar regras do produto de detalhes de framework, banco, busca vetorial e provedores de IA.
Isso permite testar o núcleo do sistema sem depender de Docker, Qdrant, PostgreSQL ou LLM real.

## Camadas

### Domain

Contém entidades, value objects e interfaces estáveis:

- `Assistant`
- `Document`
- `Conversation`
- `ChatMessage`
- contratos de repositório
- contratos de embeddings, vector store e LLM

### Application

Contém casos de uso e serviços de aplicação:

- criar e listar assistentes
- registrar documentos
- ingerir documentos
- enviar mensagem para um assistente
- recuperar histórico

### Infrastructure

Implementa detalhes externos:

- persistência PostgreSQL
- client Qdrant
- geração local de embeddings
- adapters de LLM
- grafo conversacional com LangGraph

### API

Expõe a aplicação via FastAPI:

- rotas HTTP
- schemas de request/response
- injeção de dependências
- tratamento de erros de borda

## Regra de Dependência

Dependências apontam para dentro:

`api -> application -> domain`

`infrastructure -> application/domain`

O domínio não deve importar FastAPI, SQLAlchemy, Qdrant, LangGraph ou SDKs de LLM.

## Evolução RAG Enterprise

A evolução mantém as quatro camadas e a regra de dependência. O conteúdo abaixo é **planejado**,
exceto o que a Fase 1 já entregou.

### Já Implementado (Fase 1)

- **Domain**: `EvaluationItem`, `EvaluationItemResult`, `EvaluationMetrics`, `EvaluationReport`,
  as funções `recall_at_k`, `mean_reciprocal_rank` e `first_relevant_rank` e a porta `AnswerJudge`.
- **Application**: `EvaluateAssistantUseCase` e `CompareEvaluationReportsUseCase`, com seus DTOs.
- **Infrastructure**: `evaluation` (leitor do conjunto de referência em JSON Lines, juiz de
  fidelidade por LLM, armazenamento de relatórios) e `observability` (formato de log em JSON e
  identificador de requisição por contexto).
- **API**: middleware que aceita, gera e devolve o cabeçalho `X-Request-ID`.
- **Ponto de entrada**: `python -m src.cli.evaluate`.

As camadas de domínio e aplicação registram eventos apenas com a biblioteca padrão `logging`; o
formato JSON é instalado na borda, pela API e pelo comando de avaliação.

### Domain (acréscimos)

- `AuthenticatedUser`, `AccessPolicy`
- `Citation`
- `Document` com estado, versão e restrição de grupos
- novas portas: `TokenVerifier`, `DocumentChunker`, `SparseEmbeddingGateway`, `RerankerGateway`,
  `IngestionJobQueue`, `DocumentFileStorage`, `UsageLimiter`
- novos contratos de repositório: permissões, auditoria, consumo e feedback
- portas existentes estendidas: `EmbeddingGateway` (documento e consulta), `VectorStoreGateway`
  (busca híbrida, filtro, alias, exclusão por documento) e `LLMGateway` (trechos com metadados,
  streaming e consumo de tokens)

### Application (acréscimos)

- reindexar a base de um assistente
- processar job de ingestão, excluir, substituir e reprocessar documento
- definir grupos de assistente e de documento
- consultar auditoria e consumo
- registrar feedback de resposta
- conversar com citações, com e sem streaming

Todos os casos de uso passam a receber o `AuthenticatedUser` e a consultar a `AccessPolicy`.

### Infrastructure (acréscimos)

- verificador de token do Keycloak
- embeddings com sentence-transformers, BM25 e reranker cross-encoder, todos locais
- chunker estrutural e OCR
- fila de ingestão em PostgreSQL e armazenamento de arquivos em volume
- rastreamento e métricas
- migrações versionadas

### API (acréscimos)

- dependência de autenticação e verificação de papel em todos os routers, exceto `/health`
- rota de streaming do chat

### Pontos de Entrada

Além da API HTTP, há pontos de entrada que invocam diretamente a camada de aplicação: o
**comando de avaliação**, já existente em `src/cli`, e o **worker de ingestão**, previsto. Nenhum deles contém regra de
negócio.

### Regra de Dependência

Permanece inalterada. O domínio não importa FastAPI, SQLAlchemy, Qdrant, LangGraph, bibliotecas de
JWT, sentence-transformers nem OpenTelemetry.
