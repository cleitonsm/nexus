# Campanha — candidato `validacao-final-rc5` (2026-10-21): interrompida na V6

Commit `9f0e288`. V0 e V1 vieram da `rc4` (sem mudança de código do backend e do frontend entre as duas).

| Etapa | Resultado |
|---|---|
| V2 | OK |
| V3 | OK: integração sem pulos, CT-53, CT-54 e CT-56 |
| V4 | OK |
| V5 | PENDENTE (manual) |
| V6 | FALHA na avaliação 1 de 3: `KeyError: 'metrics'` em `_store_and_compare` |

A avaliação rodou com o modelo oficial (128 chamadas ao `gemini-3.8-flash`, todas concluídas) e a conexão do LLM
permaneceu correta depois da V3 (a correção da `rc4` funcionou).

**Causa (defeito do comando de avaliação):** `JsonEvaluationReportStore.load_latest` escolhia o último `*.json` da
pasta em ordem alfabética; desde a calibração de 2026-10-20 a pasta tem `calibracao.json`, que vem depois de
`20261020-...json`. O comando tentou comparar com a calibração e parou antes de gravar o relatório.

**Correção (`2e99500`, candidato `rc6`):** só contam os arquivos `AAAAMMDD-HHMMSS-<commit>.json` (teste unitário
novo). Na revisão das etapas seguintes: o `quality-gate.sh` (V8) rodava os unitários sem `scripts/` e `docs/`, como
a V2 da `rc1`; corrigido no mesmo commit. A `rc6` muda o código do backend: repetir da V1 (reconstrução da imagem).
