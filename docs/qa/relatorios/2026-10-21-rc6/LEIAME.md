# Campanha — candidato `validacao-final-rc6` (2026-10-21): interrompida na V6

Commit `c85f36d`.

| Etapa | Resultado |
|---|---|
| V1 | OK (imagem reconstruída com a correção do `load_latest`) |
| V2, V3, V4 | OK |
| V5 | PENDENTE (manual) |
| V6 | FALHA na avaliação 1 de 3: `TimeoutError: The read operation timed out` |

A avaliação fez 79 chamadas ao `gemini-3.8-flash` (p50 4,4 s; p95 6,7 s; máximo 19,1 s); a 79ª, uma reescrita de
pergunta com histórico, passou do limite de 30 s.

**Causa (defeito do produto):** o tempo esgotado na leitura escapava do cliente do LLM como `TimeoutError` cru, e não
como `LLMProviderError`. Por isso pulava o fallback da reescrita (RF-36), que trata `RuntimeError`, e parava a
avaliação; no chat, o mesmo caso virava 500.

**Correção (`8b20b1e` e `ec276e8`, candidato `rc7`, SPEC-009 D6):** o tempo esgotado vira `LLMProviderError`, sem nova
tentativa (D2). Por decisão do autor, a avaliação repete uma vez, depois de 5 s, o item com falha do LLM; o relatório
registra os itens repetidos (`item_retries`). Pela revisão de 2026-10-21, a `rc7` é o último candidato antes de nova
revisão de escopo.
