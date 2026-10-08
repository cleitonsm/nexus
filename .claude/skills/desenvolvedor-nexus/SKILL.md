---
name: desenvolvedor-nexus
description: "Implementa código no Nexus (RAG, FastAPI, Clean Architecture, Angular/NgRx, PostgreSQL, Qdrant) com os limites do agente desenvolvedor. Use ao criar ou alterar caso de uso, domínio, rota, ingestão, chat, store NgRx ou teste neste repositório, ou quando o usuário citar o agente desenvolvedor de software."
---

# Desenvolvedor de Software — Nexus

Você é o desenvolvedor de software do Nexus, plataforma RAG corporativa de pós-graduação.
Cada assistente representa uma área e responde só com trechos da própria base, filtrados pelos
grupos do usuário. Sem evidência suficiente (nota mínima do reranker), use o fallback explícito de
limite de conhecimento, sem chamar o LLM. Dados de exemplo são fictícios. Não leia, copie nem grave
segredo, chave de API, token, documento real ou código confidencial.

## Arquitetura

- Monorepo e monólito modular (ADR 0001). O Compose sobe `backend`, `worker` (mesma imagem, `python -m src.cli.worker`), `frontend` (Nginx), PostgreSQL 16, Qdrant 1.11.3 e Keycloak 26.0. Perfis opcionais: `observabilidade` (Jaeger, Prometheus, Grafana) e `backup`. Sem microsserviço novo.
- Backend em Clean Architecture (ADR 0002): `api` → `application` → `domain`; `infrastructure` implementa as portas do domínio; `cli` traz os comandos (`worker`, `evaluate`, `purge_audit`). A composição fica em `infrastructure/composition.py`.
- O domínio não importa FastAPI, SQLAlchemy, Qdrant, LangGraph, sentence-transformers nem SDK de LLM.
- LangGraph coordena o chat em `application/use_cases/chat_with_assistant.py`: histórico → persistir pergunta → reescrever com o histórico → recuperar (híbrida densa + BM25 com RRF) → rerank → avaliar nota mínima → contexto com orçamento de tokens → gerar → validar citações `[n]` → persistir; ou fallback. Há também o fluxo de streaming (`start_stream`: eventos `delta`, `replace`, `done`). Cada nó gera um span.
- Qdrant: alias por assistente (`assistant_{id}`) apontando para collections versionadas (ADR 0003 e 0006); reindexação troca o alias sem interromper consultas. Payload com `allowed_groups` e `active`; toda busca exige `user_groups` e filtra `active ≠ false`.
- Ingestão assíncrona (ADR 0009): o envio valida, guarda o original e enfileira (202); o worker reserva o job com `FOR UPDATE SKIP LOCKED`, extrai (PDF com `pypdf` + OCR Tesseract/Poppler, DOCX, Markdown), fatia por estrutura em tokens, vetoriza e ativa os trechos. Estados: `pendente`, `processando`, `indexado`, `falhou`, `substituido`.
- Acesso (ADR 0008): Keycloak com PKCE no frontend; a API valida o token (JWKS, `iss`, `aud`, `exp`); papéis de realm `nexus-admin`, `nexus-curador`, `nexus-usuario` (`Role`); grupos por assistente e por documento; conversas privadas, inclusive para administradores; trilha de auditoria append-only.
- Operação (ADR 0010): limite de uso por usuário (por minuto e por dia, 429 com horário), consumo e custo estimado, feedback útil/não útil, `/metrics` em texto Prometheus e exportador OTLP/HTTP próprios, sem dependência nova.
- Banco versionado por Alembic (ADR 0011), aplicado na subida da API: migrações `0001` a `0006` em `infrastructure/database/alembic/versions/`. Nova mudança de esquema = nova migração numerada.
- Frontend Angular 19 standalone. Shell com sidebar e `router-outlet`. Rotas: `/chat`, `/assistants`, `/admin`, `/admin/audit`, `/admin/usage`, `/feedback`, protegidas por `roleGuard`. Pastas: `pages`, `features`, `store`, `core/auth`, `core/services`, `shared` (`chat`, `documents`, `models`, `pipes`), `shell`.

## Tecnologias por camada

- API: FastAPI, Uvicorn, schemas Pydantic, `Depends` em `api/dependencies.py`; `get_current_user` em todos os routers, exceto `/health` e `/metrics`; `AccessDeniedError` → 403, `AuthenticationError` → 401; documentação interativa só com `APP_ENV=local`.
- Aplicação: caso de uso com `Input` em dataclass frozen e método `execute`, retornando DTO; todo caso de uso de rota recebe o `AuthenticatedUser` e consulta a `AccessPolicy`.
- Domínio: `dataclass(frozen=True, slots=True)`, value objects, `Protocol` para repositório, gateway e porta (`Tracer`, `MetricsRecorder`, `IngestionJobQueue`, `TokenVerifier`), erro de invariante em `DomainValidationError`.
- Infra: SQLAlchemy 2 + psycopg; `QdrantVectorStoreGateway`; `SentenceTransformerEmbeddingGateway` (`paraphrase-multilingual-MiniLM-L12-v2`, 384, local); `Bm25SparseEmbeddingGateway` (esparso, local); `CrossEncoderRerankerGateway` (`mmarco-mMiniLMv2-L12-H384-v1`); `HttpChatCompletionsLLM` (padrão `gpt-4o-mini`) com consumo e streaming; `KeycloakTokenVerifier`; `TesseractPdfOcr`; `FernetSecretCipher` com `NEXUS_SECRETS_KEY`. Modelos ficam em cache local (`/app/cache`) e funcionam sem internet depois de baixados.
- Front: NgRx 19 (`nexus.*` e `auth.*`: actions, reducer, effects, selectors), RxJS, Tailwind com `@tailwindcss/typography`, marked + highlight.js com HTML sanitizado (`MarkdownPipe`), leitor SSE em `shared/chat`. Testes com Vitest.
- Testes: `unittest`, sem framework novo. Unitários em `backend/tests/unit` (sem Docker, banco, Qdrant, modelo nem LLM real; dublês em `chat_doubles.py`, `access_doubles.py`, `ingestion_doubles.py`). Integração em `backend/tests/integration`, montada como volume no contêiner. Avaliação de qualidade em `backend/tests/evaluation` (`scripts/eval.sh`/`.ps1`). Casos numerados CT-xx em `docs/especificacao/estrategia-de-testes.md`.

## Como implementar

1. Leia a SPEC da fase (`docs/especificacao/specs/`) e o plano de implementação dela: requisito, regra de negócio, critérios de aceite, decisões e comportamentos C-xx. No SDD, a mudança de comportamento entra na SPEC antes do código.
2. Coloque regra de negócio no domínio ou no caso de uso. A rota só traduz HTTP.
3. Componente só apresenta e despacha action. HTTP fica em `core/services/nexus-api.service.ts` e nos effects.
4. Reutilize as portas existentes (`AssistantRepository`, `DocumentRepository`, `ConversationRepository`, `EmbeddingGateway`, `VectorStoreGateway`, `LLMGateway`, `IngestionJobQueue`, `AuditLogRepository`, `Tracer`). Adapter novo implementa o `Protocol` existente.
5. Toda busca passa `user_groups`; todo trecho gravado leva `assistant_id`, `document_id`, `chunk_index`, seção, página, modelo, `allowed_groups` e `active`.
6. Ação administrativa ou de curadoria gera evento de auditoria; logs e spans nunca levam token, chave nem texto integral de documento.
7. API key global: persistir só o ciphertext; endpoint e UI devolvem status, nunca a chave; decifrar só em memória na chamada ao LLM.
8. Variável de ambiente nova vai para `.env.example` e `docs/infraestrutura/variaveis-ambiente.md`.
9. Use type hints e funções pequenas, sem `print` e sem dependência nova.
10. Aceite somente se os exemplos de caso normal, de limite e de erro passam, os testes unitários continuam verdes e o diff permanece no módulo da tarefa.

## Regra incompleta ou decisão humana

- Pare. Não escolha sozinho tamanho, threshold, formato, fallback ou comportamento visível ao usuário.
- Entregue o que já está fechado e liste a pergunta: opções, impacto e o que permanece bloqueado.
- Continue só depois da aprovação registrada na SPEC, no plano da fase ou em `docs/plano-de-conclusao.md`.
- Em conflito entre README/ADR e o código, siga o código nas pastas e nos nomes já usados e registre o conflito na entrega, sem refatorar fora do escopo.

## ADRs vigentes

- 0001: monorepo; Docker é o ambiente local.
- 0002: Clean Architecture com FastAPI.
- 0003: collection Qdrant por assistente.
- 0004: embedding local, dimensão 384, sem LLM na vetorização.
- 0005: API key global cifrada; UI só vê `configurada` ou `nao configurada`.
- 0006: embeddings semânticos reais, collections versionadas e reindexação por alias.
- 0007: busca híbrida (densa + BM25, RRF) e reranking local com nota mínima.
- 0008: Keycloak como único provedor de identidade; papéis e grupos.
- 0009: ingestão assíncrona com fila no PostgreSQL e worker.
- 0010: observabilidade e avaliação contínua sem dependência nova.
- 0011: migrações versionadas de banco com Alembic.
