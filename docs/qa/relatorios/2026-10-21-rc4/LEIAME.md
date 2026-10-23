# Campanha — candidato `validacao-final-rc4` (2026-10-21): interrompida na V6

Commit `8fbd923`.

| Etapa | Resultado |
|---|---|
| V0 | OK |
| V1 | 1ª tentativa: FALHA de ambiente (o DNS do Docker Desktop não resolvia `registry-1.docker.io` depois da suspensão; resolvido com `wsl --shutdown`). 2ª: OK |
| V2 | OK |
| V3 | OK: 146 testes de integração sem pulos (inclusive o CT-40 com aquecimento e a lista de grupos real), CT-53, CT-54 e CT-56 |
| V4 | OK: `npm ci`, `npm test`, build de produção e `npm audit` (registro), no container `node:22` |
| V5 | PENDENTE (manual) |
| V6 | FALHA na avaliação 1 de 3: `LLM provider is unreachable` |

**Causa da V6 (defeito de teste, não do produto):** `test_assistant_isolation` e `test_ocr_container` (este
também roda no CT-54) apontam a conexão do LLM da pilha para o `FakeLLMServer` (`modelo-simulado`) e não a
restauram; o CT-56 "restaura" o valor que encontrou, que já era o simulado. A V6 tentou o servidor simulado,
já desligado (`Name or service not known`). A chave do autor não foi alterada (os testes da chave usam dublês).

**Correção (`e036926`):** `stack_support.preserve_llm_settings` guarda e restaura a conexão nos dois testes; a
V6 passa a reprovar relatório gerado com outro modelo que não o oficial (`check_eval_reports --model`, PC-D8).
