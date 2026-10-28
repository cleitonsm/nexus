# Validação da SPEC-013 no Docker (P8) — 2026-10-28

Rodada oficial: `scripts/validation/spec-013-p8.ps1` sobre o commit `79227cb`, pilha do Compose no ar
(`docker compose up -d --build`, migrações `0010` e `0011` aplicadas na subida). Executada pelo autor,
analisada com apoio de IA generativa. Os `*.log` da rodada oficial entram com `git add -f`
(o `.gitignore` exclui `*.log`), como nas campanhas anteriores. `resumo.md` é a saída do script; este `LEIAME.md` é a análise.

| Etapa | Casos | Resultado |
|---|---|---|
| Subida, migrações, chave "Padrão" na tela, chat respondendo | D10, T9 | OK (autor) |
| `npm test` e `npm run build` (`strictTemplates`) | CT-110 | OK (autor) |
| Integração do backend (toda a pasta) | CT-107, CT-108, CT-109 e os anteriores | **159 testes, OK, nenhum pulado** |
| Varredura de vazamento | CT-56 | **OK**: `leaks: []`, `control_failures: []` |
| E2E (Playwright, 1 worker) | E1, CT-81 a CT-84, CT-87, CT-88, RNF-36, FE-04 | **17 de 17** |
| Avaliação sem configuração gravada | CT-111 | **Sem regressão de recuperação** (ver abaixo) |
| Duas credenciais reais (OpenAI e Gemini) | CT-112 | Adiado pelo autor |

## CT-111 — avaliação

Três execuções por conjunto: linha de base da véspera (`f2bca04`), rodada exploratória (`25bc66d`) e
rodada oficial (`79227cb`). Todos os parâmetros vieram do ambiente
(`retrieval_origins` = `default` em todos), LLM pela credencial "Padrão" (`gemini-3.8-flash`, sem recuo),
`baseline_comparable: true`.

| Conjunto | recall@5 | MRR | Fidelidade | Fallback | Citação |
|---|---|---|---|---|---|
| `nexus-docs` (base → oficial) | 1,000 → 1,000 | 0,890 → 0,890 | 0,895 → 0,947 | 1,00 → 1,00 | 0,864 → 0,864 |
| `nexus-docs-ampliado` | 0,984 → 0,984 | 0,901 → 0,909 | 1,000 → 0,983 | 0,90 → 0,90 | 0,952 → 0,952 |
| `normativo-ficticio` | 1,000 → 1,000 | 1,000 → 1,000 | 0,917 → 0,917 | 0,75 → 0,75 | 1,000 → 1,000 |

O script marcou falha no `nexus-docs` da rodada oficial: o portão do RN-14 compara com a execução
anterior, a exploratória, que teve fidelidade 1,000; a oficial teve 0,947 (18 de 19 respostas fiéis).
Entre as duas só mudaram arquivos de teste E2E; recuperação idêntica. É variação do juiz por LLM, não
regressão da SPEC-013: a fidelidade ficou acima da linha de base da véspera (0,895) e da meta do
RNF-20 (0,90). O fallback de 0,75 do `normativo-ficticio` é anterior à SPEC-013 e não mudou.

## Ocorrências da rodada

- **E2E na primeira execução: 4 falhas, nenhuma de produto.** Os arquivos rodavam em paralelo, e
  logins simultâneos de `admin.nexus` (e depois de `curadora.rh`) foram recusados pela proteção contra
  força bruta do realm, que mostra "senha inválida"; o teste de XSS lia o HTML durante uma navegação.
  Correção em `79227cb`: `workers: 1` no `playwright.config.ts` e espera do chat no teste de XSS. A
  proteção do realm não foi alterada.
- **Aviso do pydantic na integração** (`UnsupportedFieldAttributeWarning` para `repr=False`): vem dos
  validadores por campo que o FastAPI monta para os modelos de entrada. O `repr` dos próprios modelos
  (`CreateLLMCredentialRequest`, `UpdateLLMCredentialRequest`) continua sem a chave — conferido com o
  pydantic 2.13. Sem impacto no RN-39.
- **CT-108**: o filtro de grupos na busca só densa está coberto no Qdrant real
  (`test_filter_applies_to_the_dense_and_to_the_sparse_prefetch`); o de `active` vem do mesmo objeto de
  filtro que o adaptador aplica às duas pré-buscas, sem teste dedicado à busca só densa.
