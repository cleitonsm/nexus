# Rodada de integração no Docker — 2026-10-15/16

Registro da primeira execução real da suíte de integração e do frontend sobre a pilha do Compose. **Não é
a campanha oficial** (V0 a V8): não há commit etiquetado, e a execução foi feita aos poucos, com correções
entre as rodadas. Serve de evidência intermediária e de ponto de partida para o `RESUMO.md` da campanha.

Ambiente: Docker Compose local do autor (PostgreSQL 16, Qdrant 1.11.3, Keycloak 26, backend e worker
reconstruídos com `docker compose build backend worker`), `qdrant-client` 1.11.3, Node 22 (imagem `node:22`).
Os testes de integração rodam no serviço `backend` com `backend/tests/integration` montado; os de pilha
real usam `KEYCLOAK_INTERNAL_URL` (`http://keycloak:8080`).

## Resultado final por item

| Item | Caso | Resultado |
|---|---|---|
| Rotas HTTP com dublês (`test_api_routes`) | RF-48, RF-50, RF-51, RF-54, CT-75/76 (conforme os docstrings) | 14 testes ok |
| Auditoria, permissões e busca com restrição (`test_access_control_storage`) | D6 (purga), SPEC-004 | ok (35 testes junto com `test_api_routes`) |
| Fluxo completo (`test_full_stack_flow`) | CT-50 | ok |
| Isolamento entre assistentes (`test_assistant_isolation`) | CT-51 | ok |
| Conferência PostgreSQL × Qdrant (`test_consistency_check`) | CT-57 | ok |
| OCR em português no container (`test_ocr_container`) | CT-39 (RF-53) | ok |
| Upload de 25 MB em até 2 s (`test_upload_latency`) | CT-40 | ok (PDF e DOCX de ~25,3 MB) |
| `alembic upgrade head`, `alembic check`, downgrade da `0008` e novo upgrade | CT-49 | ok; `check` sem diferenças |
| Trilha de auditoria no banco de desenvolvimento antes/depois da `0008` | CT-49 | 96 linhas, `md5` inalterado, `details` em JSONB, 2 gatilhos presentes, `UPDATE` bloqueado |
| Frontend (`npm test`, Vitest) | FE-01 a FE-05, CT-21, CT-32 | 16 arquivos, 149 testes ok |
| Unitários do backend (na nuvem, sem Docker) | — | 662 ok, 1 pulado; `ruff --select F,E9` limpo |

## Defeitos achados e o que foi feito

| # | Achado | Causa | Correção |
|---|---|---|---|
| 1 | `POST .../chat/stream` respondia 200 e falhava depois | a recuperação rodava de forma preguiçosa, dentro do fluxo | a rota puxa o primeiro evento antes de responder; os erros viram status HTTP |
| 2 | Resposta 409 de duplicidade sem a chave `detail` | o corpo `{detail, code}` achatava o objeto | `error_body` mantém `detail` como objeto |
| 3 | Testes de worker falhavam (`renew`) e de consumo (`UsageSettings`) | dublês desatualizados | dublês corrigidos |
| 4 | Migração `0008`: `json` ≠ `jsonb` nos testes | imagem do backend antiga | rebuild da imagem |
| 5 | Purga de retenção bloqueada pelo gatilho | o banco de desenvolvimento tinha uma versão antiga de `audit_events_append_only()` | migração `0009_reassert_audit_guard` (idempotente) |
| 6 | Rotas `/documents/{id}` retornavam 404 em `test_api_routes` | o app de teste não montava `document_access_router` | `setUp` corrigido |
| 7 | Testes de pilha: "Connection refused" ao pedir token | `KEYCLOAK_URL` aponta para `localhost` dentro do container | `stack_support` prefere `TEST_KEYCLOAK_URL`, depois `KEYCLOAK_INTERNAL_URL` |
| 8 | CT-40: 413 para os arquivos de teste | os geradores passavam do tamanho pedido (PDF 28,2 MB, DOCX 27,7 MB para 24 MiB) | `corpus.make_fitting`, teto de 25 MiB menos 256 KiB |
| 9 | CT-39: texto do OCR com `X`/`k` no lugar de acentos | a fonte embutida do Pillow não tem os glifos acentuados | fonte TrueType com checagem de cobertura |
| 10 | CT-39: o chat caía no fallback | ver o achado de produto abaixo | pergunta específica no teste; valor do corte não alterado |

## Achado de produto: nota mínima de relevância

`scripts/diagnostico_reranker.py` mede a nota do reranker (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`,
sigmoide) para o trecho indexado do CT-39:

| Pergunta | Trecho inteiro | Só a frase | Controle irrelevante |
|---|---|---|---|
| "Qual o prazo da prestação de contas?" | **0,1940** | 0,9768 | 0,0683 |
| "Qual o prazo para a prestação de contas das despesas de viagem?" | 0,9958 | 0,4453 | 0,0369 |
| "prazo prestação de contas" | **0,2559** | 0,9453 | 0,0536 |

Com `RELEVANCE_MIN_SCORE=0,5`, o trecho correto é descartado quando a pergunta é curta. O irrelevante nunca
passa de 0,07. **A nota varia mais com a formulação da pergunta do que com a relevância do trecho**, e o
corte de 0,5 estava alto para esse modelo.

## Calibração (CT-22) e decisão

Curva sobre o `nexus-docs` (27 itens, 5 fora do escopo), sem chamar o LLM. **Decisão do autor: `RELEVANCE_MIN_SCORE=0,10`.**

| Critério | Resultado com 0,10 |
|---|---|
| Perguntas dentro do escopo que chegam ao LLM | 82% |
| Perguntas fora do escopo que terminam em fallback | 100% |
| Maior nota entre as fora do escopo | 0,044 (margem de 2,3× até o corte) |

Ressalvas: só há 5 itens fora do escopo; refazer a calibração com o `nexus-docs-ampliado` (20 fora do escopo)
depois da validação do curador. Um corte menor aumenta o risco de contexto fraco chegar ao LLM; conferir a
fidelidade na V6. Após alterar o `.env`, rodar `docker compose up -d backend worker`.

## Não executado nesta rodada

`test_migrations` (CT-49 completo), `test_keycloak_real` (CT-52), `test_nginx_proxy` (CT-55), CT-53, CT-54,
CT-56, Playwright (FE-06/FE-07), `retrieval_latency.py`, `reindex_under_load.py`, CT-47 e CT-48, a calibração
(CT-22) e a avaliação com LLM (V6). Estão na seção 11 do
[runbook](../../runbook-itens-dependentes-do-autor.md).
