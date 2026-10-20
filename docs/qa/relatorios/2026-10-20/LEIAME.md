# Rodada da V3 no Docker — 2026-10-20

Primeira execução da etapa V3 pelo orquestrador (`scripts/validation/run-all.sh --only V3`) depois do alinhamento
de `1c0ded5`: toda a pasta `backend/tests/integration` com as montagens da rodada de 2026-10-15/16 e reprovação de
teste pulado. **Não é a campanha oficial** (sem commit etiquetado); serve de evidência intermediária.

## Resultado final

| Item | Resultado | Evidência |
|---|---|---|
| Integração do backend (145 testes, nenhum pulado) | ok, sobre `cc2e24a` | `V3-testes-de-integracao-do-backend-.log` |
| CT-53 resiliência do worker | aprovado | `V3-CT-53-resiliencia-do-worker-.log` |
| CT-54 operação sem internet | aprovado | `V3-CT-54-operacao-offline-.log` |
| CT-56 varredura de vazamento | **zero vazamento, zero falha de controle**, sobre `675abc7` com `view-users` aplicado ao realm | `ct56/leakage_scan.json` |

O `resumo.md` registra a execução anterior do orquestrador, em que o CT-56 falhou por ambiente (ver abaixo); o CT-56
foi repetido isoladamente com o comando do runbook.

## Defeitos achados e corrigidos

| # | Achado | Causa | Correção |
|---|---|---|---|
| 1 | `run-all.ps1` falhava com `execvpe(/bin/bash)` | usava o lançador do WSL sem distribuição | `8ba07fa`: prefere o bash do Git for Windows |
| 2 | CT-04: avaliação saía com código 3 e *deadlock* na limpeza | o worker da pilha reservava parte dos jobs do piloto | `c71abd7`: `seed_documents` acompanha pelo banco os jobs de outro worker (prazo D7); SPEC-007 |
| 3 | CT-52: `'admin' not found in ['nexus-admin']` | teste com o nome errado do papel | `fd53cd1` |
| 4 | CT-55: CSP ausente em `/health` | o teste olhava uma rota com `add_header` próprio | `fd53cd1`: confere a página `/` |
| 5 | CT-12: 613 mil `TypeError` | função interna com o mesmo nome do helper | `fd53cd1` |
| 6 | CT-05: linha com `request_id` nulo | linha do httpx do lado do cliente | `fd53cd1` |
| 7 | CT-56: `Connection refused` | o CT-54 religava a pilha sem esperar | `cc2e24a`: `up -d --wait` |
| 8 | CT-56: `422 unknown groups: rh` | **defeito de produto**: com só `query-groups`, o Keycloak 26 lista os grupos vazios e todo envio com grupo era recusado | `db4e051`/`675abc7`: `view-users` na conta de serviço (SPEC-009 D5, decisão do autor); teste real `GroupDirectoryRealTests` |

## Testes manuais (2026-10-20, tarde)

| Caso | Resultado |
|---|---|
| CT-70 Gemini real | **aprovado**: na tela de Administração, provedor "Gemini (Google)", "Testar LLM" respondeu "Comunicacao com a LLM validada usando a API key armazenada. Modelo: gemini-4-argon \| Resposta: OK" |
| CT-77 aviso de versão do Qdrant | **parcial**: nenhum `incompatible`/`client version` nos logs da V3 (o cliente 1.11.3 criado no container falaria com o servidor 1.11.3); 14 testes de busca híbrida e alias ok. Falta `docker compose logs backend worker` da subida. Observação: aparece `UserWarning: Api key is used with an insecure connection` (chave do Qdrant em HTTP dentro da rede do Compose), esperado no ambiente local |

## Ainda não executado

CT-77 (logs de subida), CT-47/48 (V8), V7 (RNF-03/16/18), FE-06/FE-07 (Playwright),
o novo `GroupDirectoryRealTests` (roda na próxima V3) e a V6 (avaliação com LLM).
