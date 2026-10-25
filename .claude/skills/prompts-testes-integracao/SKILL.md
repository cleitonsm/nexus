---
name: prompts-testes-integracao
description: Biblioteca de prompts para gerar casos de teste de integração do Nexus (cenários de fluxo, erros de autorização e dados de isolamento) e transformá-los em testes em backend/tests/integration.
argument-hint: <cenarios|erros|dados> <endpoint ou fluxo alvo>
---

# Prompts para testes de integração

Argumentos: `$ARGUMENTS`. O primeiro termo escolhe o tipo de prompt, o resto é o alvo (ex.: `erros POST /conversations/{id}/chat`).

Os três tipos se completam: **cenários** ampliam a cobertura, **erros** ampliam a diversidade e **dados** dão repetibilidade. O texto completo de cada prompt, a saída esperada e o teste real que ela originou estão em [prompts.md](prompts.md).

| Tipo | Gera | Teste de referência |
|---|---|---|
| `cenarios` | fluxo feliz entre API → PostgreSQL → Qdrant → LLM | `test_chat_citations.py` |
| `erros` | casos negativos de autenticação e autorização (401/403/404) | `test_access_control_api.py` |
| `dados` | documentos fictícios disjuntos e pergunta discriminante | `test_assistant_isolation.py` (CT-51) |

## Passos

1. Leia a SPEC do alvo em `docs/especificacao/specs/` e a rota em `backend/src`. Sem SPEC, pare: pelo SDD, o comportamento entra na SPEC antes do código.
2. Pegue o prompt do tipo pedido em `prompts.md` e preencha os `{{campos}}` com dados reais do alvo: endpoint, filtros (`user_groups`, `active`), papéis (`nexus-admin`, `nexus-usuario`) e códigos de erro.
3. Rode o prompt e gere a lista de casos no formato que ele exige (ID, pré-condição, passos, resultado esperado, justificativa).
4. **Revise contra a SPEC**: descarte casos com status HTTP ou regra que contradiga a especificação, e marque os que já existem em `backend/tests/integration`.
5. Escolha o nível de cada caso:
   - **API com dublês**: `TestClient` com `dependency_overrides`, como em `test_chat_citations.py` e `test_access_control_api.py`;
   - **pilha real**: helpers de `stack_support.py` (`Api`, `token_for`, `FakeLLMServer`, `stack_available`), como em `test_assistant_isolation.py`.
6. Escreva os testes com `unittest`, nomes `test_<comportamento>` em inglês, docstring citando CT/RF/RN, `subTest` para matrizes (rota × token) e `addCleanup` para remover o que foi criado. Só o LLM é simulado na pilha real.
7. Valide: `cd backend && ruff check --select F,E9 src tests`. Para a pilha real: `docker compose up -d --build` e rode o arquivo do teste.

## Regras

- Dados sempre fictícios; nunca documento, token ou `.env` reais.
- Toda busca testada deve provar o filtro por `user_groups` e `active`.
- Um teste de integração que simula tudo vira teste unitário: simule só a fronteira externa (LLM).
