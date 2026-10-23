---
name: spec-to-code
description: Implementa uma SPEC do Nexus no fluxo SDD — requisitos e critérios primeiro, testes CT-xx em seguida, depois o código e a verificação.
disable-model-invocation: true
argument-hint: <SPEC-00N> [item ou comportamento C-xx específico]
---

# Da SPEC ao código (SDD)

Alvo: `$ARGUMENTS`. Siga também a skill `desenvolvedor-nexus`.

1. **Ler.** Abra `docs/especificacao/specs/<SPEC>-*.md` e o `<SPEC>-plano-de-implementacao.md`. Extraia requisitos (RF/RNF), regras de negócio, critérios de aceite, decisões (D-x) e comportamentos C-xx no escopo. Se o pedido muda comportamento que a SPEC não descreve, proponha primeiro o ajuste na SPEC e espere confirmação.
2. **Planejar.** Liste em poucas linhas as camadas afetadas (domínio, caso de uso, infra, rota, store NgRx, componente) e os casos CT-xx de `docs/especificacao/estrategia-de-testes.md` que cobrem o escopo; crie CT novos se faltarem.
3. **Testes primeiro.** Escreva os testes unitários em `backend/tests/unit` (`unittest`, dublês existentes, sem banco/Qdrant/modelo/LLM reais) e, no frontend, specs Vitest de reducer, selector e effect. Rode e confirme que falham pelo motivo esperado.
4. **Implementar.** Regra no domínio ou no caso de uso; rota só traduz HTTP; componente só apresenta e despacha action; HTTP no `nexus-api.service.ts` e nos effects. Mudança de esquema → `/new-migration`.
5. **Verificar.**
   - `cd backend && ruff check --select F,E9 src tests && python -m unittest discover -s tests/unit`
   - `cd frontend && npm test && npm run build`
   - Se tocou no pipeline RAG, chame o subagente `rag-quality-reviewer`; para o resto do backend, `architecture-guard`.
6. **Fechar.** Marque na SPEC/plano o que foi concluído e resuma: critérios atendidos, CT-xx cobertos, pendências.
