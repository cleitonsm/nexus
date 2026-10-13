# Plano de Implementação — SPEC-006 Operação e Governança

**Spec**: [SPEC-20261007-006](SPEC-006-operacao-e-governanca.md) (Aprovada em 2026-10-08)
**ADR**: [0010 — Observabilidade e avaliação contínua](../../arquitetura/adrs/0010-observabilidade-e-avaliacao-continua.md) (ajustada pelas decisões D1, D2 e D4)
**Status do plano**: Código de P1 a P8 entregue em 2026-10-08; fechamento (P10, etapa E6) entregue em 2026-10-13; a validação no Docker (P9) está pendente
**Data**: 2026-10-08
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## 0. Andamento

| Pacote | Situação em 2026-10-08 | Verificado por |
|--------|------------------------|----------------|
| P1 Domínio | Entregue: `domain/usage.py` (`TokenUsage`, `LLMCompletion`, `LLMStreamChunk`, `LLMPricing`, `UsageRecord`, `UsageLimits`, `evaluate_usage_limits` com janelas deslizantes de 60 s e 24 h); `domain/feedback.py` (`MessageFeedback` com envio, revisão e exportação para `EvaluationItem`); `domain/prompt_injection.py`; portas `Tracer` e `MetricsRecorder` (`domain/observability.py`); `UsageLimiter`, `UsageRecordRepository`, `UsageSettingsRepository`, `FeedbackRepository`; `LLMGateway.generate_with_usage` e `generate_stream`; erros `UsageLimitExceededError` e `InvalidFeedbackStateError`; ações de auditoria novas | Testes unitários (CT-41, CT-42, CT-43) |
| P2 Aplicação | Entregue: `UsageGovernance` (limite e registro de consumo); chat com limite antes de qualquer etapa, consumo somado da reescrita e da resposta, trecho por nó do grafo, sinalização de injeção (auditoria e métrica, sem bloquear) e `start_stream` (eventos `delta`, `replace`, `done`); prompt do assistente e regra de citação nas instruções de sistema (RN-31); casos de uso de avaliação (enviar, listar, revisar, exportar) e de consumo e limites | Testes unitários |
| P3 Persistência | Código entregue: migração `0006_operations` (`usage_records`, `app_settings`, `message_feedback`); repositórios e limitador em `operations_repositories.py`; `ConversationRepository.get_message` | Nada: SQLAlchemy e Alembic não estavam disponíveis fora do Docker |
| P4 Observabilidade | Entregue: `SpanTracer` e exportador OTLP/HTTP JSON; `MetricsRegistry` no formato de texto do Prometheus; filtro de atributos (RNF-25); adaptadores rastreados para LLM, Qdrant e Keycloak; trecho e métricas por requisição HTTP; `/metrics` | Testes unitários (formato OTLP, formato Prometheus, filtro, contexto do streaming) |
| P5 LLM | Entregue: `HttpChatCompletionsLLM` com consumo (`usage`) e streaming (`stream_options.include_usage`); trechos recuperados delimitados na mensagem do usuário e escapados sem distinção de maiúsculas; dublês com consumo | Testes unitários (montagem das mensagens e leitura do streaming) |
| P6 API | Código entregue: `POST /conversations/{id}/chat/stream` (SSE; erros antes do primeiro byte mantêm o status HTTP; 429 com `Retry-After` e `retry_at`); `POST /messages/{id}/feedback`; `GET /feedback`, `POST /feedback/{id}/review`, `GET /feedback/export` (JSONL); `GET /admin/usage`; `GET`/`PUT /admin/usage-limits`; `GET /metrics` | Testes de integração escritos (`test_operations_api.py`, streaming em `test_chat_citations.py`), não executados: FastAPI não estava disponível |
| P7 Docker, backup e CI | Entregue: perfil `observabilidade` (Jaeger, Prometheus, Grafana com painel provisionado); perfil `backup` com `backup.sh`, `restore.sh` e agenda diária; Nginx sem buffer na rota de streaming e `/api/metrics` → 404; `.github/workflows/ci.yml`; `scripts/quality-gate.sh`; versões de `qdrant-client`, `langgraph` e demais dependências fixadas pelo `pip freeze` da imagem | `docker compose config` com os perfis; sintaxe POSIX dos scripts; nada executado |
| P8 Frontend | Código entregue: chat em streaming (pergunta imediata, texto progressivo, fontes ao final); botões útil / não útil com comentário e aviso de que o curador verá a conversa; mensagem do limite de uso com o horário de liberação; telas **Consumo e limites** (`/admin/usage`) e **Avaliações** (`/feedback`); menu por papel | Lógica pura e reducer: 14 testes novos com substitutos locais do Vitest e do NgRx; templates e componentes só por revisão; sem build |
| P9 Validação no Docker | Não iniciado | — |

Verificação feita: **497 testes unitários do backend passam** (424 anteriores e 73 novos), fora do
Docker, em Python 3.13, com o LangGraph substituído por um dublê. A verificação estática não
encontrou nomes indefinidos nem imports sem uso, e todos os módulos de `backend/src` importam com as
bibliotecas externas substituídas por simulacros.

**Não verificado**: migração 0006, repositórios, rotas e SSE reais, Nginx, exportação ao Jaeger,
Prometheus e Grafana, backup e restauração, workflow do GitHub, build do Angular e as telas.

## 1. Decisões aplicadas

| # | Escolha | Onde |
|---|---------|------|
| D1 | Jaeger, Prometheus e Grafana em perfil opcional | `compose.yaml`, `infra/observability/` |
| D2 | Rastreamento e métricas próprios, sem dependência nova | `infrastructure/observability/tracing.py` e `metrics.py` |
| D3/D6 | 20 por minuto e 500 por dia, ajustáveis na tela; 0 desliga | `UsageLimits`, `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_DAY`, `app_settings` |
| D4 | GitHub Actions para unitários e estáticas; avaliação local | `.github/workflows/ci.yml`, `scripts/quality-gate.sh` |
| D5/D9 | Backup diário, 7 dias, serviço no Compose | `infra/docker/backup.Dockerfile`, `scripts/backup*.sh`, `scripts/restore.sh` |
| D7 | USD, tabela do `gpt-4o-mini` | `LLM_PRICE_*` |
| D8 | Útil / não útil + comentário | `MessageFeedback`, chat |

## 2. Comportamentos definidos na implementação

Escolhas de detalhe, aprovadas pelo autor como estão em 2026-10-08 (C2 e C9 ficam como limitações
aceitas, decisão PC-D7 do [plano de conclusão](../../plano-de-conclusao.md)):

- **C1** O limite conta perguntas registradas em `usage_records`, inclusive as que falharam ou
  tiveram o cliente desconectado. Os registros sobrevivem à exclusão da conversa, para que apagar
  conversas não zere o limite.
- **C2** A verificação do limite e o registro não são atômicos: duas perguntas simultâneas do
  mesmo usuário no último lugar da janela podem passar juntas.
- **C3** A pergunta bloqueada pelo limite não chega ao grafo (nada é gravado na conversa) e entra
  na auditoria como `chat.rate_limited`, sem o texto.
- **C4** Na avaliação negativa, a pergunta e a resposta são copiadas para `message_feedback` para o
  curador, que não tem acesso à conversa privada (RN-24). A tela avisa o usuário antes do envio.
  A avaliação positiva não guarda texto.
- **C5** Avaliação já revisada pelo curador não pode ser alterada pelo usuário (409).
- **C6** O detector de injeção só sinaliza (auditoria `chat.prompt_injection_suspected` com
  documento, trecho e padrões, sem o texto); a resposta segue. A defesa principal é estrutural:
  regras no sistema, trechos delimitados na mensagem do usuário e delimitadores do próprio
  documento escapados.
- **C7** No streaming, o texto transmitido é o da geração; se a validação das citações reprovar, um
  evento `replace` troca o texto pelo fallback. Sem contexto relevante, o LLM não é chamado e só o
  fallback é enviado.
- **C8** O cliente que desconecta no meio do streaming conta como pergunta `cancelled`, com o
  consumo já gasto.
- **C9** `/metrics` não exige token e fica fora do proxy público; no ambiente local continua
  acessível pela porta 8000 publicada.
- **C10** Falha de backup é tentada de novo em 1 hora.
- **C11** O CI usa `ruff` (só no workflow, não na imagem) para a verificação estática.

## 3. Como validar no Docker

1. Copiar para o `.env`, se ele sobrescrever valores, as variáveis novas do `.env.example`
   (`RATE_LIMIT_*`, `LLM_PRICE_*`, `OTEL_*`, `BACKUP_*`).
2. `docker compose up -d --build`. A subida aplica a migração `0006_operations`.
3. Chat: enviar uma pergunta e ver o texto aparecer em partes, com as fontes no final; marcar
   "não útil" com comentário; entrar como `curadora.rh` e validar a avaliação em **Avaliações**;
   exportar o JSONL.
4. Limite: como `admin.nexus`, gravar 2 por minuto em **Consumo e limites**; fazer três perguntas
   seguidas e ver a mensagem com o horário de liberação; conferir o consumo na mesma tela.
5. Observabilidade: `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` no `.env`,
   `docker compose --profile observabilidade up -d`, uma pergunta, e procurar o `X-Request-ID` da
   resposta no Jaeger; ver o painel do Grafana.
6. Backup: `docker compose --profile backup run --rm backup backup.sh` e o roteiro de
   [backup-e-restauracao.md](../../infraestrutura/backup-e-restauracao.md) num ambiente limpo
   (CT-47).
7. Testes de integração no contêiner: `test_operations_api.py` e `test_chat_citations.py`.
8. `scripts/quality-gate.sh` e o primeiro push com o workflow do GitHub.

## 4. Fora deste plano

- Lacunas médias citadas na ordem de trabalho (reindexação no worker, R18, tela de conversas
  arquivadas, seleção de grupos): não implementadas nesta entrega.
- Medição formal do RNF-01 e dos demais requisitos: campanha final (Parte B).

## 5. Fechamento da Fase 6 (2026-10-13, etapa E6)

Escopo aprovado pelo autor: CT-46 a CT-48 e os três itens do backlog do Cartographer
(`.cartographer/backlog.md`, 2026-10-13) que são defeitos de funcionalidades desta fase: fix-6
(streaming preso), fix-9 (backup inconsistente) e a parte de imagens do fix-12. O refresh de token
do fix-12 é da Fase 4 e ficou fora. Decisões D10 a D13 na [SPEC](SPEC-006-operacao-e-governanca.md).
C1 a C11 já tinham sido aprovados na etapa E3 sem pedido de mudança.

| Pacote | Entrega | Verificado por |
|--------|---------|----------------|
| P10.1 Pausa da ingestão (D10) | `IngestionPause` (domínio), porta `IngestionPauseRepository`, `ingestion_paused` (aplicação), `PostgresIngestionPauseRepository` (chave `ingestion_pause` em `app_settings`, sem migração nova); o worker consulta a pausa antes de cada volta e registra `ingestion.worker.paused`/`resumed` | 6 testes unitários (`test_ingestion_pause.py`); 3 de integração com PostgreSQL (`test_ingestion_pause_storage.py`, não executados) |
| P10.2 Backup consistente (D10) | `backup.sh` pausa, espera os jobs em andamento, copia, libera (também em erro) e tira as contagens do dump restaurado num banco temporário e do arquivo de documentos; `restore.sh` remove a pausa herdada do dump; `pipefail` onde o shell suporta | `scripts/validation/backup-scripts-check.sh` executado com PostgreSQL 16 real e Qdrant simulado (7 verificações), também como job `backup-scripts` do CI |
| P10.3 CT-46 | Pergunta pela rota normal e pela de streaming com `SpanTracer`, exportador OTLP, `MetricsRegistry`, logs JSON e o cliente HTTP real do LLM contra um servidor local; nenhum token, chave, texto de documento nem pergunta nas saídas | `test_sensitive_data_leak.py` (3 testes) executado; um vazamento proposital num atributo foi detectado; passo próprio no CI |
| P10.4 CT-47 (D11) | `scripts/validation/backup-restore.sh`: backup do ambiente atual, projeto Compose limpo `nexus-ct47`, restauração, `check_consistency` e busca (`backend/tests/validation/restored_search.py`), evidências em `docs/qa/relatorios/<data>-ct47/` | Sintaxe; não executado (exige Docker) |
| P10.5 CT-48 | `test_regression_gate.py` (linha de base inflada vira regressão; queda dentro da tolerância e primeira execução passam) e `scripts/validation/regression-gate.sh` (código de saída real da avaliação) | 3 testes unitários executados; roteiro não executado (exige Docker) |
| P10.6 Streaming interrompido (D13) | `ServerSentEventsReader.finish` entrega o último evento; `chat-stream-flow.ts` (fim sem evento final vira erro; cancelamento); ações `cancelChatStream`/`chatStreamCancelled`; botão "Parar" e cancelamento ao sair do chat; a conversa é recarregada para mostrar a pergunta gravada | 2 specs do leitor, 5 do fluxo e 1 do reducer, com substitutos do Vitest e do NgRx |
| P10.7 Imagens no markdown (D12) | `neutralizeRemoteContent` depois do sanitizador: `<img>` vira `[imagem: alt]`, links ganham `rel="noopener noreferrer"`; Nginx com `Content-Security-Policy: img-src 'self' data:` | 4 specs de `markdown-safety` e 1 do `MarkdownPipe`, com substitutos |

Verificação feita em 2026-10-13: **545 testes unitários do backend passam** (536 anteriores e 9
novos), mais os 3 do CT-46; `ruff` sem achados; todos os módulos importam com as bibliotecas
externas simuladas; 85 testes do frontend em 8 specs (13 novos) passam com substitutos; as demais specs não foram executadas nesta sessão.

**Não verificado**: CT-47 e CT-48 no Docker, o teste de integração da pausa com PostgreSQL, o
worker pausando de fato, o Nginx com o CSP, o botão "Parar" e o build do Angular.

### Comportamentos definidos no fechamento

- **C12** A pausa vale para ingestão e reindexação, inclusive para devolver jobs vencidos à fila. O
  chat, os envios (que só enfileiram) e as telas continuam funcionando durante o backup.
- **C13** O backup espera os jobs em andamento por até `INGESTION_JOB_TIMEOUT_SECONDS` (600 s, D7
  da SPEC-005). Job de ingestão reservado há mais tempo que isso conta como abandonado. Reindexação
  longa demais adia o backup, e o serviço tenta de novo em 1 hora (C10).
- **C14** O prazo da pausa (`BACKUP_PAUSE_MAX_SECONDS`, 3600 s) só vale para um backup morto sem
  liberar a pausa.
- **C15** A resposta interrompida mostra "A resposta foi interrompida antes do fim. A pergunta ficou
  na conversa; tente novamente." O botão "Parar" não mostra mensagem.
- **C16** Uma imagem sem texto alternativo vira `[imagem]`. Links que já tenham `rel` ficam como
  estão.

