# Campanha — candidato `validacao-final-rc1` (2026-10-20): interrompida

Commit `a5775a7`. Os comandos foram colados de uma vez, sem a pausa para cadastrar a chave do LLM.

| Etapa | Resultado | Causa | Correção (`2906ac2`, candidato `rc2`) |
|---|---|---|---|
| V0 | FALHA na varredura de `bypassSecurityTrustHtml` (o `down -v` não chegou a rodar) | o nome aparece só num dublê de teste, `frontend/src/app/shared/pipes/markdown.pipe.spec.ts` | a varredura ignora `*.spec.ts` |
| V1 | OK (sobre o ambiente não limpo) | — | — |
| V2 | FALHA: 650 testes, 1 falha e 1 erro | `test_check_eval_reports` e `test_validate_items` leem `scripts/` e `docs/`, não montados no container | a V2 monta `./scripts` e `./docs` na raiz do container |
| V4 (prevista) | não executada | chamaria `npm` no Windows, que não o tem | `npm_frontend` usa o container `node:22` quando não há npm no host |

Nenhum defeito do produto. Conforme a seção 9 do plano de validação, a campanha recomeça no candidato `rc2`,
gravando em `docs/qa/relatorios/2026-10-20-rc2/` (`NEXUS_REPORT_DIR`). Cada execução do orquestrador regrava o
`resumo.md`; o desta pasta é o da V2.
