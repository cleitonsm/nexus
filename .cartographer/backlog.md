# Backlog — Nexus (Cartographer, 2026-10-13)

Itens com arquivo e verificação. ✅ = conferido por mim no código; 🔎 = achado do revisor, ainda não reconferido (o agente de correção deve **verificar se o problema existe antes de mexer**; se não existir, pular é o resultado certo).
Verificação padrão: `scripts/quality-gate.sh` (não executado por mim). Faça numa branch separada.

```fix-1
summary: Impedir que o cliente grave mensagens com role assistant/system no histórico
severity: P0
files: backend/src/api/schemas/conversations.py, backend/src/application/use_cases/manage_conversation.py
location: backend/src/api/schemas/conversations.py:31-39 ; backend/src/application/use_cases/manage_conversation.py:123-146
status: confirmado (schema)
description: |
  AddMessageRequest.role aceita user, assistant e system. As mensagens gravadas entram no historico
  enviado ao LLM nas perguntas seguintes e podem receber feedback; AddMessageUseCase nao aplica
  limite de uso, acesso do assistente nem auditoria.
fix: |
  Verifique primeiro se o frontend usa essa rota com role diferente de user.
  Se nao usa: restringir o enum a USER (ou remover a rota). Rejeitar role != user no use case tambem.
  Aplicar a mesma checagem de acesso do chat.
verification: teste unitario novo para role=assistant retornando 422; scripts/quality-gate.sh
```

```fix-2
summary: Validar tamanho do upload antes de carregar o arquivo inteiro em memoria
severity: P0
files: backend/src/api/routes/documents.py
location: backend/src/api/routes/documents.py:116 ; :230
status: confirmado
description: |
  await file.read() carrega o arquivo todo; o limite max_file_bytes so e checado depois, dentro do use case.
  Um upload gigante esgota a memoria do processo da API.
fix: |
  Rejeitar cedo por Content-Length e ler em blocos ate max_file_bytes + 1, retornando 413.
  Tambem mover a chamada sincrona assistant_repository.get_by_id (linha ~111) para fora do loop de eventos.
verification: teste de integracao enviando arquivo acima do limite e esperando 413 sem ler tudo
```

```fix-3
summary: Renovar a reserva e conferir o dono do job na ingestao e na reindexacao
severity: P0
files: backend/src/application/use_cases/process_ingestion.py, backend/src/application/services/ingestion.py, backend/src/application/use_cases/reindex_assistant.py, backend/src/infrastructure/database/repositories.py
location: process_ingestion.py:399 ; ingestion.py:50 ; reindex_assistant.py:191,208,229-235
status: achado do revisor, nao reconferido
description: |
  Reserva fixa de 600 s sem renovacao; complete/retry/fail/save nao verificam que o worker ainda e o dono.
  Documento grande com OCR pode ser reprocessado por outro worker; no reindex um worker pode apagar a
  colecao que o outro esta montando.
fix: |
  Adicionar renew(job, until) chamado por pagina/lote e tornar as atualizacoes condicionais em
  (id, attempts, status='reserved'); abortar se afetar 0 linhas. No reindex, nao executar discard/swap
  se a posse foi perdida.
verification: teste com dois workers simulados e reserva expirada; scripts/quality-gate.sh
```

```fix-4
summary: Falhar na inicializacao com segredos padrao e publicar so o necessario no compose
severity: P0
files: compose.yaml, .env.example, infra/keycloak/nexus-realm.json
location: compose.yaml:7-9,11,69,88,141-142,167,186,197,213 ; .env.example:74 ; nexus-realm.json:114,123-224
status: confirmado (portas e senhas); severidade depende de onde o compose roda
description: |
  Todas as portas estao publicadas em todas as interfaces (inclui Postgres, Qdrant, Keycloak start-dev,
  Prometheus, Jaeger e o backend, que expoe /metrics). .env.example e carregado como env_file obrigatorio
  com credenciais publicas. Os 5 usuarios do realm, inclusive o admin, usam a senha nexus-dev (temporary:false).
fix: |
  Confirmar com o dono se o compose e apenas local. Publicar so o frontend; demais em 127.0.0.1:PORTA.
  Exigir segredos com ${VAR:?} e recusar NEXUS_SECRETS_KEY padrao quando APP_ENV != local.
  Separar os usuarios de teste em nexus-realm.dev-users.json e marcar senha como temporary:true.
verification: docker compose config sem variaveis em branco; curl em host:8000/metrics a partir de outra maquina deve falhar
```

```fix-5
summary: Tornar a troca de colecao no reindex atomica com a atualizacao dos documentos
severity: P1
files: backend/src/application/use_cases/reindex_assistant.py, backend/src/infrastructure/database/repositories.py
location: backend/src/application/use_cases/reindex_assistant.py:178-185
status: achado do revisor, nao reconferido
description: |
  Apos o swap do alias os documentos sao salvos um a um; uma falha no meio deixa o alias na colecao nova
  com metadados antigos, o indice aparece como desatualizado e novos uploads ficam bloqueados.
fix: |
  Criar DocumentRepository.save_many em uma unica transacao e registrar estado explicito
  "swap feito, banco nao sincronizado" que permita retomar sem novo reindex completo.
verification: teste que injeta falha apos o swap e confirma que uploads continuam possiveis
```

```fix-6
summary: Evitar stream de chat preso e permitir cancelamento
severity: P1
files: frontend/src/app/store/nexus.effects.ts, frontend/src/app/core/services/nexus-api.service.ts, frontend/src/app/shared/chat/chat-stream.ts
location: nexus.effects.ts:237-267 ; nexus-api.service.ts:215 ; chat-stream.ts:18
status: achado do revisor, nao reconferido
description: |
  Se o stream termina sem evento done/error, chatStream e loading.sendChat ficam ativos para sempre.
  Nao existe acao de cancelar ao sair da tela. O leitor perde o ultimo evento quando nao ha linha em branco final.
fix: |
  Emitir falha quando o stream completar sem evento terminal; adicionar cancelChatStream com takeUntil;
  descarregar o buffer restante ao fechar a resposta. (CRLF nao e necessario: o backend usa \n\n.)
verification: spec novo em chat-stream.spec.ts e nexus.reducer.spec.ts; ng test
```

```fix-7
summary: Rollback em falha de commit e Unit of Work para escritas multi-repositorio
severity: P1
files: backend/src/infrastructure/database/repositories.py, backend/src/infrastructure/database/operations_repositories.py
location: repositories.py:67,185,537 ; operations_repositories.py:64,292
status: achado do revisor, nao reconferido
description: |
  Cerca de 14 caminhos de escrita fazem commit sem rollback; falha deixa a sessao inutilizavel em workers
  de longa duracao. Cada repositorio commita sozinho, entao auditoria e acao nao sao atomicas.
fix: |
  Passo 1 (pequeno): helper _commit() com rollback e traducao de IntegrityError.
  Passo 2 (maior, decidir antes): mover o commit para a camada de aplicacao via Unit of Work.
verification: teste que forca IntegrityError no commit e reutiliza a sessao
```

```fix-8
summary: Listar conversas sem carregar todas as mensagens
severity: P1
files: backend/src/infrastructure/database/repositories.py, backend/src/application/use_cases/list_conversations.py
location: repositories.py:118,134-165
status: achado do revisor, nao reconferido
description: |
  list_by_assistant e list_archived carregam todas as mensagens de todas as conversas, sem paginacao;
  save() recarrega o historico completo.
fix: |
  Criar list_summaries(assistant_id, owner, limit, cursor) selecionando so colunas da conversa
  (message_count por subquery) e manter o carregamento completo so em get_by_id.
verification: teste com 200 conversas verificando numero de queries e ausencia de selectinload(messages)
```

```fix-9
summary: Backup consistente entre Postgres, Qdrant e arquivos, com restore testado
severity: P1
files: scripts/backup.sh, scripts/backup-common.sh, .github/workflows/ci.yml
location: scripts/backup.sh:28-52 ; ci.yml:84-88
status: achado do revisor, nao reconferido
description: |
  Os tres armazenamentos sao copiados em momentos diferentes com o worker escrevendo; counts.txt e
  gerado depois, da base viva. CI so roda sh -n nos scripts, nunca um restore.
fix: |
  Pausar o worker durante o backup (ou ordem Postgres -> Qdrant sob pausa de escrita), gerar counts.txt a
  partir da fonte do dump, adicionar set -o pipefail e um job de CI backup+restore com servicos efemeros.
verification: job de CI novo que restaura e compara contagens
```

```fix-10
summary: Timeout e limites nos extratores de documento
severity: P1
files: backend/src/infrastructure/documents/text_extraction.py, backend/src/infrastructure/documents/ocr.py, backend/src/infrastructure/documents/structured_extraction.py
location: text_extraction.py:139,153,168 ; ocr.py:61 ; structured_extraction.py:252
status: achado do revisor, nao reconferido
description: |
  antiword, catdoc e soffice rodam sem timeout; um arquivo ruim trava o worker e o proximo que pegar o job.
  OCR reescreve e reparseia o PDF inteiro a cada pagina escaneada, sem limite de paginas.
fix: |
  Helper unico _run_tool(cmd, timeout) com perfil isolado do LibreOffice e erro retryable dedicado ao timeout;
  limite de paginas e de memoria para PDF/DOCX.
verification: teste com executavel falso que dorme alem do timeout
```

```fix-11
summary: Classificar falhas de ingestao por erro explicito, nao por tipo de excecao
severity: P2
files: backend/src/application/use_cases/process_ingestion.py, backend/src/application/services/document_indexing.py
location: process_ingestion.py:152-160 ; document_indexing.py:87
status: achado do revisor, nao reconferido
description: |
  Qualquer ValueError vira "documento ilegivel" permanente; divergencia de contagem de vetores do provedor
  de embeddings falha sem nenhuma nova tentativa e com motivo enganoso.
fix: |
  Criar UnreadableDocumentError e TransientServiceError levantados pelos extratores e gateways.
verification: testes de classificacao para PDF corrompido, timeout de OCR e contagem de vetores errada
```

```fix-12
summary: Restringir markdown do LLM (imagens remotas) e proteger o refresh de token
severity: P2
files: frontend/src/app/shared/pipes/markdown.pipe.ts, frontend/src/app/core/auth/auth.service.ts, frontend/src/app/core/auth/oidc-client.ts
location: markdown.pipe.ts:39 ; auth.service.ts:112-125 ; oidc-client.ts:155
status: achado do revisor, nao reconferido
description: |
  Tags img remotas sobrevivem a sanitizacao: um documento com prompt injection pode fazer o LLM emitir uma
  URL que vaza contexto ao renderizar. Qualquer falha no refresh (inclusive de rede) forca novo login.
fix: |
  Renderer do marked que remove/reescreve imagem e adiciona rel="noopener noreferrer" aos links; definir
  CSP com img-src restrito no Nginx. Expirar a sessao so em invalid_grant; repetir com backoff em erro de rede.
verification: markdown.pipe.spec.ts com imagem remota; spec de refresh com erro de rede
```

```fix-13
summary: Indices, CHECKs e passive_deletes no banco
severity: P2
files: backend/src/infrastructure/database/models.py, backend/src/infrastructure/database/alembic/versions/
location: models.py:43-50,98,145,200-204,217,272,419,424
status: achado do revisor, nao reconferido
description: |
  Faltam indices em conversations(owner_user_id, assistant_id, updated_at), messages(conversation_id, created_at),
  usage_records(assistant_id), documents(replaces_document_id). Filtro em audit_events.details->>'assistant_id'
  usa coluna json (scan completo). Colunas de status sem CHECK. Cascatas sem passive_deletes.
fix: |
  Migration 0008 com os indices, details para jsonb com indice de expressao, CHECKs e passive_deletes=True;
  espelhar em models.py. Verificar antes que as migrations ja aplicadas em outros ambientes nao divergem.
verification: alembic upgrade head e alembic check em banco limpo
```

```fix-14
summary: Padronizar erros HTTP e evitar oraculo de enumeracao de assistentes
severity: P2
files: backend/src/api/errors.py, backend/src/api/routes/conversations.py, backend/src/api/routes/documents.py, backend/src/api/routes/index.py, backend/src/api/routes/admin.py
location: conversations.py:124,363,368 ; documents.py:111 ; index.py:60 ; admin.py:170
status: achado do revisor, nao reconferido
description: |
  Seis rotas checam existencia do assistente antes da permissao (404 vs 403), contradizendo a RN-24 ja
  aplicada a conversas. LLM nao configurado retorna 422 em vez de 503; falhas upstream devolvem 502 com
  o texto bruto da excecao; ha quatro formatos de resposta de erro.
fix: |
  Mover a checagem de existencia para depois do AccessControl nos use cases (404 para ausente e proibido);
  handlers globais por tipo de erro com envelope unico {detail, code}; nao ecoar texto de excecao do upstream.
verification: testes de integracao existentes de rotas + novos casos de 403/404 equivalentes
```

## Andamento (2026-10-14)

| Item | Situação |
|------|----------|
| fix-1, 2, 3, 4 | Feitos (SPEC-007). |
| fix-6, fix-9, fix-12 (imagens) | Feitos (SPEC-006, E6). |
| fix-10 | Feito: `_run_tool` com limite de 120 s nos extratores `.doc`, perfil próprio do LibreOffice, estouro no OCR tratado como falha passageira. **Fora**: limite de páginas/memória (muda o que o produto aceita; decisão do autor). |
| fix-11 | Feito: `UnreadableDocumentError` (definitiva) e `TransientServiceError` (nova tentativa); contagem de vetores errada e estouro de ferramenta agora são repetidos. |
| fix-12 (refresh) | Feito: só resposta 4xx do Keycloak encerra a sessão; rede ou 5xx repete (1 s, 3 s) e depois tenta a cada 30 s sem derrubar o usuário. Spec novo em `oidc-client.spec.ts`, não executado. |
| fix-5, 7, 8, 13 | Pendentes: mexem em SQLAlchemy/PostgreSQL e migração, sem como validar na nuvem. Fazer com o Docker (fix-7 passo 1 e fix-13 primeiro). |
| fix-14 | Pendente: o envelope único de erro muda o contrato com o frontend; decidir o formato antes. |

## Andamento (2026-10-14, segunda leva)

Decisões do autor: erro HTTP `{detail, code}`; limite de OCR de 200 páginas (`OCR_MAX_PAGES`); fix-7 só o passo 1.

| Item | Situação |
|------|----------|
| fix-10 (páginas) | Feito: `OCR_MAX_PAGES=200` conta só páginas sem texto; acima disso o documento falha como ilegível, antes de qualquer OCR. |
| fix-7 (passo 1) | Feito: `commit_or_rollback` em todos os repositórios (`database/transactions.py`). Unit of Work fica fora. |
| fix-5 | Feito em parte: `DocumentRepository.save_many` grava todos os documentos do reindex em uma transação. Não criei o estado "swap feito, banco fora de sincronia": se a gravação falhar o job termina como falhou. |
| fix-8 | Feito em parte: listagens de conversas (`list_by_assistant`, `list_archived`) não carregam mais as mensagens (contagem por subconsulta). Sem paginação/cursor. |
| fix-13 | Feito, **não executado**: migração `0008_indexes_and_constraints` (4 índices, `audit_events.details` em JSONB com índice de expressão, CHECK de status em 4 tabelas) e `passive_deletes`. Validar com `alembic upgrade head`, `alembic check` e o downgrade. |
| fix-14 | Feito, **não executado** (sem FastAPI na nuvem): todo erro sai como `{detail, code}` (`api/errors.py`, `api/error_codes.py`); assistente inexistente responde 403 a quem não pode usá-lo (404 só para administrador), nas rotas de criar conversa, enviar documento e índice; falha do LLM no chat não repete o texto do provedor; LLM sem chave no teste do admin passa de 422 a 503. O teste de chave do administrador continua mostrando a causa (é diagnóstico, só administrador). |
