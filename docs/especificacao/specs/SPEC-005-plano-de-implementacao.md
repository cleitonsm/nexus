# Plano de Implementação — SPEC-005 Ingestão e Ciclo de Vida de Documentos

**Spec**: [SPEC-20261007-005](SPEC-005-ingestao-e-ciclo-de-vida.md) (Aprovada em 2026-10-08)
**ADR**: [0009 — Ingestão assíncrona com fila em PostgreSQL](../../arquitetura/adrs/0009-ingestao-assincrona.md) (Aceita em 2026-10-08)
**Status do plano**: Código de P1 a P8 entregue em 2026-10-08; tabelas em PDF (parte do RF-53) adiadas pela decisão D11 (2026-10-08); a validação no Docker está pendente
**Data**: 2026-10-08
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## 0. Andamento

| Pacote | Situação em 2026-10-08 | Verificado por |
|--------|------------------------|----------------|
| P1 Domínio | Entregue: `DocumentStatus` e transições validadas em `Document` (`start_processing`, `mark_indexed`, `retry_later`, `mark_failed`, `request_processing`, `mark_replaced`); campos de estado, versão, tamanho e autor; `IngestionJob`; porta `IngestionJobQueue`; `find_by_hash`; `DocumentFileStorage.delete`; `VectorStoreGateway.delete_by_document` e `set_document_active`; `VectorChunk.active`; erros `DuplicateDocumentError`, `InvalidDocumentStateError`, `IngestionInProgressError`; ações de auditoria novas | Testes unitários (CT-33) |
| P2 Aplicação | Entregue: envio que só valida, guarda e enfileira; `ProcessNextIngestionJobUseCase` e `RequeueExpiredIngestionJobsUseCase` (worker); `ReplaceDocumentUseCase`, `ReprocessDocumentUseCase`, `DeleteDocumentUseCase`, `GetDocumentUseCase`; `IngestionSettings` (D7); citações de fonte removida; reindexação ajustada | Testes unitários (CT-34 a CT-36) |
| P3 Persistência | Código entregue: migração `0005_document_lifecycle`, `IngestionJobModel`, `PostgresIngestionJobQueue` (`FOR UPDATE SKIP LOCKED`, documento e job na mesma transação), repositório de documentos com estado | Nada: SQLAlchemy e Alembic não estavam disponíveis fora do Docker |
| P4 Extração e OCR | Entregue: `TesseractPdfOcr` (Poppler gera a imagem, Tesseract reconhece) para páginas de PDF sem texto; PDF corrompido vira erro definitivo. Tabelas em PDF: **adiadas** (D11 = b) | Testes unitários com o Tesseract real (idioma `eng`), inclusive envio → worker → `indexado` |
| P5 Qdrant | Código entregue: payload `active`, índices de `document_id` e `active`, filtro `active ≠ false` em toda busca, `delete_by_document`, `set_document_active` | Nada: `qdrant-client` não estava disponível |
| P6 API | Código entregue: `POST /assistants/{id}/documents` responde 202 (409 em duplicidade, com o documento existente); `GET /assistants/{id}/documents` com estado; `GET` e `DELETE /documents/{id}`; `PUT /documents/{id}/content`; `POST /documents/{id}/reprocess`; `document_available` nas citações de `GET /conversations/{id}` | Nada: FastAPI não estava disponível |
| P7 Worker e Docker | Entregue: `python -m src.cli.worker`; serviço `worker` no Compose (mesma imagem, volumes `documents_data` e `backend_cache`, `stop_grace_period: 90s`); Tesseract (`por`, `eng`) e Poppler na imagem; variáveis novas; Nginx aceita 26 MB | Sintaxe do `compose.yaml`; o worker e a imagem não foram executados |
| P8 Frontend | Código entregue: estado, versão, tamanho e motivo da falha na lista; excluir com confirmação, substituir e reprocessar; consulta a cada 3 s enquanto houver pendente ou processando (para ao sair da tela ou trocar de assistente); aviso de duplicidade; "fonte removida" nas citações | Lógica pura e reducer: 67 testes (55 anteriores e 12 novos) com substitutos locais do Vitest e do NgRx; templates e componentes só por sintaxe; sem build |
| P9 Validação no Docker | Não iniciado | — |

Verificação feita: **424 testes unitários do backend passam** (372 anteriores, adaptados ao envio
assíncrono, e 52 novos), fora do Docker, em Python 3.13, com o LangGraph substituído por um dublê.
Os 10 testes de integração novos (fila no PostgreSQL com dois consumidores, filtro `active` e
exclusão no Qdrant) e os ajustes das rotas só rodam no container. Uma verificação estática não
encontrou nomes indefinidos, imports sem uso nem definições duplicadas novas, e todos os módulos
de `backend/src` importam com as bibliotecas externas substituídas por simulacros.

**Não verificado**: migração, repositórios, fila, adaptador Qdrant, rotas, worker, imagem com
Tesseract `por`, build do Angular e as telas. As Fases 2 a 4 também não foram validadas no Docker.

## 0.1 Como validar no Docker

1. Copiar para o `.env`, se ele sobrescrever valores, as variáveis novas do `.env.example`
   (`UPLOAD_MAX_BYTES=26214400`, `INGESTION_MAX_ATTEMPTS`, `INGESTION_JOB_TIMEOUT_SECONDS`,
   `OCR_LANGUAGES`). Um `.env` antigo com `UPLOAD_MAX_BYTES=20971520` mantém o limite de 20 MB.
2. `docker compose up -d --build`. A subida aplica a migração `0005_document_lifecycle` (os
   documentos existentes ficam `indexado`, versão 1) e inicia o serviço `worker` depois do backend.
3. `docker compose logs -f worker` deve mostrar `ingestion.worker.started`.
4. Enviar um arquivo em "Documentos e permissões": aparece "Pendente", depois "Processando" e
   "Indexado", sem recarregar. Enviar o mesmo arquivo de novo: aviso de arquivo já enviado.
5. PDF digitalizado (só imagem): deve chegar a "Indexado"; o texto vem do OCR em português.
6. Worker reiniciado: enviar um arquivo grande e, durante "Processando", `docker compose restart
   worker`. O worker conclui o job em andamento antes de parar (até 90 s). Com
   `docker compose kill worker`, o job volta à fila em até 10 minutos e é processado de novo,
   com a mesma quantidade de trechos.
7. Substituir: durante o processamento da nova versão, o chat continua citando a anterior; ao
   chegar a "Indexado", só a nova é citada. Excluir: a pergunta sobre o assunto cai no fallback e
   a conversa antiga mostra a citação como "fonte removida".
8. Testes no container:
   `docker compose run --rm --no-deps -v ./backend/tests:/app/tests backend python -m unittest discover -s tests/unit`
   e o mesmo com `-s tests/integration` (sem `--no-deps`). No container, o teste de OCR real roda.
9. Frontend: `npm ci && npm test && npm run build` em `frontend/`.

## 1. Decisões

Registradas por Cleiton Medeiros em 2026-10-08, antes do código.

| # | Decisão | Escolha | Efeito no código |
|---|---------|---------|------------------|
| D1 | Aprovação da SPEC-005, da ADR 0009 e dos comportamentos C1 a C8 | Aprovadas | — |
| D2 | Mecanismo de OCR | Tesseract e Poppler na imagem, chamados por processo | `TesseractPdfOcr`; `apt-get install poppler-utils tesseract-ocr tesseract-ocr-por tesseract-ocr-eng` no `backend.Dockerfile` |
| D3 | Limite e variáveis | 25 MB; `UPLOAD_MAX_BYTES` e `DOCUMENTS_STORAGE_PATH`, aceitando `DOCUMENT_MAX_FILE_BYTES` e `DOCUMENTS_DIR` | `composition.max_file_bytes()` e `build_file_storage()`; resolve a lacuna dos nomes |
| D4 | Estado na interface | Consulta a cada 3 s, só enquanto houver documento pendente ou processando na tela aberta | `pollDocumentStatusEffect`, `DOCUMENT_POLL_INTERVAL_MS` |
| D5 | Histórico de versões | Só a vigente; a anterior fica `substituido` | `DocumentStatus.REPLACED`; trechos e arquivo da anterior removidos ao indexar a nova |
| D6 | Armazenamento em produção | Volume local | `LocalDocumentFileStorage` (já existia) ganhou `delete` |
| D7 | Novas tentativas | 3; esperas de 30 s e 120 s; job reservado por mais de 600 s volta à fila e conta como tentativa | `IngestionSettings`; `INGESTION_MAX_ATTEMPTS` e `INGESTION_JOB_TIMEOUT_SECONDS` (esperas fixas) |
| D8 | Envio durante reindexação | Aceito; o job espera | A reserva ignora assistentes com reindexação em curso; a reindexação só copia documentos indexados |
| D9 | Arquivo idêntico | Mesmo hash no mesmo assistente (pendente, processando, indexado ou falhou) → 409 com o documento existente; nova versão idêntica → 409 | `find_by_hash`; `DuplicateDocumentError` |
| D10 | Citação de documento excluído | Mantida e marcada | `document_available: false` em `GET /conversations/{id}`; "fonte removida" na tela |

## 2. Comportamentos definidos na implementação

C1 a C8 foram aprovados com o plano (D1); C9 a C16 surgiram na implementação e foram aprovados
pelo autor como estão em 2026-10-08 (ver o [plano de conclusão](../../plano-de-conclusao.md)).

| # | Comportamento | Como ficou |
|---|---------------|------------|
| C1 | Erros definitivos | Formato não suportado, arquivo vazio, corrompido ou sem texto mesmo com OCR, idioma de OCR ausente, original não encontrado e base que exige reindexação vão direto a `falhou`. Falhas de Qdrant, banco, embedding e tempo excedido são transitórias |
| C2 | Motivo exibido | Mensagem em português por tipo de erro (`application/services/ingestion.py`); o detalhe técnico fica no log e em `ingestion_jobs.last_error` |
| C3 | Documentos anteriores | `indexado`, versão 1; os sem original não podem ser reprocessados (risco R9) |
| C4 | Exclusão durante o processamento | Permitida; o job sai junto (`ON DELETE CASCADE`). O worker confere a existência do documento antes de ativar os trechos e remove o que gravou |
| C5 | Concorrência | Um job por vez por processo; um container `worker` |
| C6 | Grupos | Gravados antes do job; a nova versão herda os grupos e os metadados da anterior |
| C7 | Auditoria | `document.deleted`, `document.replaced`, `document.reprocessed`; o worker registra `document.indexed` e `document.failed` como `system:worker` |
| C8 | Reindexação | Continua em thread na API. Recusada com 409 enquanto algum documento do assistente estiver `processando`; copia só documentos `indexado` |
| C9 | Laço do worker | Consulta a fila a cada 2 s quando vazia; a cada volta, devolve à fila os jobs vencidos. SIGTERM conclui o job em andamento antes de sair (`stop_grace_period: 90s`) |
| C10 | Quando há OCR | Só em página de PDF com camada de texto vazia; imagem a 300 dpi; cada comando tem limite de 180 s (estouro é falha transitória) |
| C11 | Versão do pipeline | `PIPELINE_VERSION` não mudou: só páginas que antes ficavam vazias passam a ter texto, e mudar a versão obrigaria a reindexar todos os assistentes. PDFs mistos já indexados só ganham as páginas digitalizadas ao serem reindexados ou substituídos |
| C12 | Regras das ações | Reprocessar só a partir de `falhou`; substituir só a versão `indexado`, uma nova versão por vez; excluir a vigente exclui a nova versão pendente; exclusão recusada (409) durante reindexação, como a troca de grupos |
| C13 | Quem consulta o estado | `GET /documents/{id}` exige gerenciar documentos do assistente (curador ou administrador), como a lista desde a Fase 4. A spec dizia "com acesso ao assistente" |
| C14 | Nome do arquivo | Envio sem extensão reconhecida é recusado (422): o worker identifica o formato pelo nome |
| C15 | Trechos ativos | Todo trecho nasce inativo e é ativado no fim do processamento (RN-27). Trechos gravados antes da fase não têm o campo e continuam nas buscas |
| C16 | Envio de vários arquivos | O efeito de envio passou a usar `mergeMap`: todos os arquivos selecionados são enviados (antes, `switchMap` cancelava os anteriores) |

## 3. Pendente de decisão

| # | Decisão | Opções | Impacto | O que fica bloqueado |
|---|---------|--------|---------|----------------------|
| D11 | Preservar tabelas de PDF com camada de texto (RF-53) | (a) Detectar colunas pelo alinhamento do texto do `pypdf` (modo de layout) e gerar bloco `TABLE`, como no DOCX; exige escolher o critério (mínimo de colunas, de linhas e de espaços entre colunas) e mudar `PIPELINE_VERSION`, o que obriga a reindexar todos os assistentes antes de novos envios. (b) Adiar para a Fase 6 ou para uma biblioteca de layout | (a) melhora respostas sobre tabelas, com custo de reindexação geral e risco de falsos positivos; (b) mantém as tabelas de PDF como texto corrido | Só a parte de tabelas do RF-53. OCR, tabelas de DOCX e Markdown já estão entregues |

**D11 decidida em 2026-10-08: (b) adiar.** As tabelas de PDF continuam como texto corrido; sem
mudança de `PIPELINE_VERSION` nem reindexação geral. Tabelas de DOCX e Markdown seguem preservadas.

## 4. Diferenças em relação ao texto da spec

- `ingestion_jobs.kind` tem `ingestao` e `reprocessamento`; `reindexacao` não é usado, porque a
  reindexação do assistente continua na API (C8).
- `DocumentRepository.update_status` não existe: o estado é gravado por `save` e, no worker,
  pela fila, junto com o job.
- `ingestion_jobs` não tem `assistant_id`: a reserva o obtém pelo documento.
- A rotina de conferência de contagens entre PostgreSQL e Qdrant (R18) não foi criada; a
  mitigação desta fase é a idempotência (trechos removidos antes de cada gravação) e o estado
  `falhou` com reprocessamento.

## 5. Testes

- Unitários (`tests/unit/test_document_lifecycle.py`, `test_ocr_extraction.py`): CT-33
  (transições), CT-34 (esperas de 30 s e 120 s, falha definitiva, recuperação, reprocessamento),
  CT-35 (worker encerrado no meio do job: trechos inativos, retomada com a mesma contagem, falha
  por tempo na última tentativa), CT-36 (duplicidade, exclusão inclusive durante o
  processamento, substituição, interação com a reindexação, citações removidas) e OCR real.
- Integração (`tests/integration/test_document_lifecycle_storage.py`, `test_api_routes.py`,
  `test_chat_citations.py`): CT-37 (dois consumidores com `SKIP LOCKED`, transação única,
  espera durante reindexação, cascata), CT-38 (filtro `active`, `delete_by_document`, trechos
  antigos sem o campo), CT-40 (rotas). CT-39 (OCR) roda como teste unitário com o Tesseract real.

## 6. Lacunas conhecidas

- Tabelas em PDF: adiadas (D11 = b); continuam como texto corrido.
- Conferência PostgreSQL × Qdrant (R18): comando sob demanda `python -m src.cli.check_consistency`
  desde 2026-10-08 (PC-D3); não roda sozinho.
- Desempenho (RNF-02: 10 MB em 60 s; RNF-17: resposta em 2 s) não medido. OCR em CPU de um PDF
  digitalizado grande pode passar dos 60 s.
- Sem tela para documentos substituídos (D5 não guarda versões para consulta).
- Corrida residual: uma reindexação iniciada entre a reserva de um job e a verificação do worker
  é detectada e o job volta à fila; a janela entre a verificação e a gravação não é bloqueada.
- Os blocos `#region agent log` foram removidos de todo o frontend em `b6aaf2f` (2026-10-08).
- A reindexação passou da thread da API para o worker em 2026-10-08 (PC-D4, migração `0007`). A
  conferência R18 virou comando (PC-D3) no mesmo dia; a aceitação das limitações (PC-D7) está na etapa E10 do
  [plano de conclusão](../../plano-de-conclusao.md).
