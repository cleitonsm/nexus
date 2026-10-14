# Runbook — itens que dependem da sua atuação

Gerado em 2026-10-14. Cada bloco é copiável no PowerShell, na raiz do repositório (`D:\Projects\nexus`).
Tudo o que pode ser feito sem o Docker já foi escrito e testado (634 testes unitários); **o que está
aqui exige a pilha no ar** e foi escrito sem nunca ter sido executado. Na primeira execução, trate
uma falha como possível defeito do próprio teste e me traga a saída.

Ordem sugerida: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Os passos 1 a 3 destravam o chat; do 4 em diante é
validação.

## 1. Recriar o banco do Keycloak (cliente de serviço `nexus-backend`)

Resolve o `503` de `/api/groups` (o realm antigo não tem o cliente). Apaga só o banco `keycloak`
(usuários e grupos criados à mão se perdem; os do arquivo do realm voltam).

```powershell
docker compose stop keycloak
docker compose exec postgres psql -U nexus -d postgres -c "DROP DATABASE keycloak;"
docker compose exec postgres psql -U nexus -d postgres -c "CREATE DATABASE keycloak;"
docker compose up -d keycloak
docker compose logs backend --since 2m | Select-String "group directory"
```

Depois de ~1 min, em `http://localhost:4200` o seletor de grupos deve listar `rh`, `financeiro`,
`diretoria`.

## 2. Reconstruir backend e worker (cliente Qdrant 1.11.3, retry do LLM, validação de grupos)

```powershell
docker compose build backend worker
docker compose up -d
# CT-77: nao pode haver aviso de versao incompativel do qdrant-client
docker compose logs backend worker | Select-String -Pattern "incompatible|versions of client and server"
docker compose logs backend --since 5m | Select-String "ERROR"
```

Sem saída nas duas últimas linhas = CT-77 aprovado para a subida. Confirme também uma indexação e uma
busca (passo 4 cobre isso).

## 3. Corrigir os documentos com o grupo "Sem restrição"

Causa do fallback em todas as perguntas. Na tela de documentos, deixe o campo de grupos **vazio**
(ou reenvie sem grupos). Conferência no Qdrant (a chave padrão é `nexus-local`):

```powershell
$body = '{"filter":{"must_not":[{"is_empty":{"key":"allowed_groups"}}]},"exact":true}'
$body | curl.exe -s -X POST "http://localhost:6333/collections/assistant-<ID_DO_ASSISTENTE>/points/count" `
  -H "api-key: nexus-local" -H "Content-Type: application/json" --data-binary "@-"
```

`"count":0` = nenhum trecho restrito. Daqui em diante o envio recusa grupo inexistente (422).

## 4. Testes de integração no Docker (CT-04, 05, 07, 10–12, 18–20, 26–31, 37–38, 44–47, 49–57, 39, 40)

Os arquivos de `backend/tests/integration` não estão na imagem; são montados. Com a pilha no ar:

```powershell
$run = 'docker compose run --rm --no-deps -e PYTHONPATH=/app:/app/integration ' +
       '-v ./backend/tests/integration:/app/integration:ro ' +
       '-v ./backend/tests/evaluation:/app/evaluation ' +
       '-v ./scripts:/app/scripts:ro backend'

# Os que ja existiam (nunca executados)
Invoke-Expression "$run sh -c 'cd /app/integration && python -m unittest -v test_api_routes test_access_control_api test_job_ownership_storage test_evaluation_command test_hybrid_search test_chat_citations test_qdrant_alias test_access_control_storage test_document_lifecycle_storage test_operations_api test_sensitive_data_leak test_request_context'"

# Os novos, da pilha real (precisam do Keycloak com os usuarios do realm de desenvolvimento)
Invoke-Expression "$run sh -c 'cd /app/integration && python -m unittest -v test_migrations test_keycloak_real test_full_stack_flow test_assistant_isolation test_consistency_check test_ocr_container test_upload_latency'"

# Nginx (CT-55): rode pelo host, o servico frontend publica a porta 4200
$env:NGINX_URL = "http://localhost:4200"
python backend\tests\integration\test_nginx_proxy.py
```

`skipped` significa que o teste não achou o serviço (nome de rede, variável) e **não** é aprovação:
procure o motivo. Os testes que alteram a conexão do LLM (`test_full_stack_flow` e afins) a restauram
no final.

## 5. Resiliência, rede isolada e vazamento (CT-53, CT-54, CT-56)

Em Git Bash (ou WSL) para os `.sh`; o de vazamento roda no container:

```bash
scripts/validation/worker_resilience.sh      # CT-53: ~3 min; usa um limite de 30 s so no roteiro
scripts/validation/offline_check.sh          # CT-54: exige Docker Compose 2.24+ e modelos ja baixados
```

```powershell
docker compose run --rm --no-deps -e PYTHONPATH=/app:/app/integration `
  -v ./backend/tests/integration:/app/integration:ro `
  -v ./backend/tests/evaluation:/app/evaluation `
  -v ./scripts:/app/scripts:ro backend `
  python /app/scripts/validation/leakage_scan.py --out /app/evaluation/reports/acesso
```

CT-56 sai com código 0 e a frase `OK: nenhum vazamento`. Qualquer linha `VAZAMENTO:` é defeito
bloqueante (meta "zero vazamento").

## 6. Frontend: Vitest (FE-01 a FE-05, CT-21, CT-32) e E2E

```powershell
cd frontend
npm ci
npm test
```

Specs novas de FE-02 (`nexus.effects.spec.ts`), FE-03 (`auth.interceptor.spec.ts`) e FE-05
(`selectors.spec.ts`) foram escritas sem rodar. Erros de tipo ou de importação nelas são esperados na
primeira vez; traga a saída. O E2E (Playwright) é opcional e está em `frontend/e2e/README.md`:

```powershell
npm install --save-dev @playwright/test
npx playwright install chromium
npx playwright test
```

## 7. Calibração da nota mínima (CT-22) — a decisão é sua

```powershell
scripts\eval.ps1 nexus-docs --no-generation     # indexa o piloto e mede recall/MRR (sem LLM)
scripts\calibrate.ps1                           # varre 0,05..0,95 sem chamar o LLM
```

A saída mostra, por nota, quanto das perguntas **dentro do escopo** ainda encontra a fonte certa e
quanto das **fora do escopo** termina em fallback, mais os itens problemáticos. Escolha o valor e
registre em `.env` (`RELEVANCE_MIN_SCORE=...`), depois `docker compose up -d backend worker`. Com o
conjunto de 27 itens (5 fora do escopo) a curva é grossa; refaça com o ampliado (passo 8).

## 8. Conjunto ampliado (82 itens, 55 rascunhos)

```powershell
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --list
# depois de revisar pergunta, resposta e fonte de cada item:
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --by "Seu Nome" --approve-all
scripts\eval.ps1 nexus-docs-ampliado
scripts\calibrate.ps1 nexus-docs-ampliado
```

Para um teste antes de validar, use `scripts\eval.ps1 nexus-docs-ampliado --allow-unvalidated`
(o relatório registra que o conjunto não foi validado). `--approve-all` assume que você leu todos.

## 9. Publicar a branch

```powershell
git status                      # confira se nao ha nada inesperado
git push origin feat/rag-enterprise
```

O remoto estava em `8518f7b`; os commits desde então ainda não foram enviados. O CI roda o que existir
em `.github/workflows` (se houver); o resultado do CI é o que indica falha de ambiente que não vi aqui.

## O que fica com você por ser decisão

- Valor final de `RELEVANCE_MIN_SCORE` (passo 7).
- Validação de cada item do conjunto ampliado (passo 8, RN-15).
- Quais itens do backlog do Cartographer implementar (recomendação no relatório desta sessão).
