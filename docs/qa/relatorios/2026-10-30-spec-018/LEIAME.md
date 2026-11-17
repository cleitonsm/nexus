# Validação da SPEC-018 (P9) — 2026-10-30 a 2026-11-04

Resumidor de documentos ([SPEC-018](../../../especificacao/specs/SPEC-018-resumidor-de-documentos.md),
[ADR 0014](../../../arquitetura/adrs/0014-documento-pessoal-e-assistente-de-sistema.md)). Rodadas executadas pelo
autor na pilha do Compose da branch `feat/spec-018-resumidor-de-documentos`, analisadas com apoio de IA generativa.
Documentos de teste: só os fictícios de `scripts/gerar_documentos_resumidor.py` (CLAUDE.md).

**Fechamento com ressalva, por decisão do autor em 2026-11-04**: a nova medição do RNF-40 com a D44, a avaliação de
não regressão e o CT-152 manual ficaram pendentes porque os créditos pré-pagos do provedor de LLM acabaram
(402 `RESOURCE_EXHAUSTED`) durante a validação. Ver "Pendências".

| Etapa | Casos | Resultado |
|---|---|---|
| Suíte unitária do backend (fora do container) | CT-139 a CT-146 | **1020 testes**; só as 2 falhas conhecidas de cópia (`test_check_eval_reports`, `test_validate_items`), anteriores à SPEC |
| API no container (`test_summarizer_api` e rotas tocadas) | CT-147, CT-127 | **82 testes, OK** |
| Integração no container (Postgres e Qdrant reais) | CT-147, CT-148, CT-149 | **20 testes, OK** (52 s) |
| Vitest e `ngc` | CT-150 | **238 de 238**; `ngc` sem erro |
| Documentos fictícios gerados no container (tokenizador real) | T10 | OK: 5 arquivos (`extenso-ficticio.pdf` com 37.799 tokens; `acima-do-teto-ficticio.docx` acima de 40.000) |
| E2E com a API simulada | CT-151 | **OK** (8,9 s) |
| E2E na pilha real, `extenso-ficticio.pdf` | CT-151, RNF-37, RNF-40 | **OK**: RNF-37 **0,19 s** (< 1 s); RNF-40 **357,6 s** (meta de 300 s, medida, não portão) |
| Nova medição do RNF-40 com a D44 | RNF-40 | **Pendente**: o resumo falhou com 402 do provedor |
| Avaliação de não regressão do assistente piloto | SPEC-001, tolerância 0,02 | **Pendente** (depende do LLM) |
| Roteiro manual, passos 56 a 65 | CT-152 | **Pendente** |

## RNF-40 e a D44

Primeira medição, antes da D44 (dados da auditoria `summary_document.summarized`, `gemini-3.8-flash`):

| Rodada | Lotes | Tokens do documento | Total | Resumo (LLM) | Extração e indexação | Tokens in / out |
|---|---|---|---|---|---|---|
| 1 | 7 | 37.799 | 356 s | 335 s | 21 s | 52.552 / 15.246 |
| 2 | 7 | 37.799 | 355 s | 339 s | 16 s | 53.598 / 15.984 |

O gargalo era o resumo: 8 chamadas em sequência (7 mini-resumos e o consolidado), cerca de 42 s cada. O E2E
tratava o RNF-40 como portão; corrigido em `4915b1b`, pois a SPEC o define como meta medida. O autor escolheu a
**D44** (até `SUMMARY_PARALLEL_CALLS = 4` chamadas simultâneas nos mini-resumos e nos grupos do terceiro nível;
consolidado depois), entregue em `9d1c681` com 3 testes unitários novos. Estimativa, sem medição: 90 a 120 s de
resumo.

## Ocorrências

- **Login do E2E sem tela do Keycloak** (2026-10-30): página em branco depois de `docker compose up -d --build`;
  o Keycloak ainda subia. Sem relação com o produto.
- **402 do provedor** (2026-10-31): `LLMProviderError ... 402 RESOURCE_EXHAUSTED: Your prepayment credits are
  depleted`. O job `resumo` esgotou as 3 tentativas e foi para "falhou"; a indexação ficou pronta e as perguntas
  seguiram liberadas, como manda a RN-64. O botão "Tentar resumir de novo" reenfileira só o resumo.
- **Comando de geração** rodado de `frontend/`: `-v ./scripts` montou uma pasta vazia. Caminho absoluto resolve.

## Pendências (ressalva do fechamento)

1. Nova medição do RNF-40 com a D44: E2E `-g "real"` com `E2E_SUMMARIZER_FILE` e a consulta da auditoria.
   Se o provedor recusar 4 chamadas simultâneas (429), reduzir `SUMMARY_PARALLEL_CALLS`.
2. Avaliação de não regressão do assistente piloto (`scripts/eval.ps1`), porque o filtro da busca no Qdrant mudou
   (escopo pessoal). Os testes do CT-148 cobrem que `active` e `user_groups` continuam aplicados.
3. CT-152 manual (passos 56 a 65 de `docs/qa/validacao-manual-rag-enterprise.md`).

## Melhoria registrada

Erros 401 e 402 do provedor são definitivos: hoje o job de resumo (e a ingestão) ainda fazem as 3 tentativas.
Tratá-los como falha sem nova tentativa economiza tempo e chamadas. Fica para uma próxima mudança, via SPEC.
