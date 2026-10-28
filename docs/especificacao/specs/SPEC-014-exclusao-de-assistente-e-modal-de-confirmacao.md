# SPEC-014 — Exclusão de assistente com a base vetorial e modal de confirmação padrão

**ID**: SPEC-20261028-014
**Status**: **Aprovada** em 2026-10-28 por Cleiton Medeiros (D1 a D3 escolhidas pelo autor; D2 e D3 são as recomendações). Código entregue em 2026-10-28. CT-118 aprovado pelo autor na pilha em 2026-10-28; CT-119 escrito em `tests/integration/test_access_control_api.py`, a executar no container do backend.
**Origem**: pedido do autor (2026-10-28): excluir um assistente e toda a base vetorial dele,
avisando antes que a base também será excluída; modal de confirmação no padrão visual do Nexus
para excluir conversas, reaproveitado na exclusão de assistentes.
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. **Sem acesso na tela.** `DELETE /assistants/{id}`, `DeleteAssistantUseCase`, a action
   `deleteAssistant` e o reducer já existem, mas nenhuma tela oferece a ação: o método
   `ShellComponent.deleteAssistant` não é chamado pelo template.
2. **Exclusão incompleta.** O caso de uso apaga o registro (o PostgreSQL apaga em cascata
   documentos, jobs, conversas, mensagens, grupos e avaliações) e a collection física para onde o
   alias aponta, mas:
   - não apaga os **originais** dos documentos no volume local (`storage_key`), que ficam órfãos;
   - não verifica **reindexação em andamento**: o worker continuaria gravando na collection nova e
     trocaria o alias depois da exclusão, recriando a base de um assistente que não existe;
   - apaga o registro antes da base: se o Qdrant falhar, o assistente some e a collection fica
     órfã, sem como repetir a exclusão pela API.
3. **Confirmação nativa.** Excluir conversa usa `window.confirm` ("localhost:4200 diz…"), fora do
   padrão visual, sem acessibilidade própria e sem como dar ênfase a consequências.

## Objetivo

Administrador exclui um assistente pela barra lateral, depois de ler que a base vetorial e os
documentos também serão excluídos e de digitar o nome do assistente. Um componente de
confirmação único serve a conversa e ao assistente.

## Decisões

| # | Escolha |
|---|---------|
| D1 | A ação fica na **barra lateral**: ícone de lixeira que aparece ao passar o mouse (ou ao focar) sobre o assistente, como já ocorre nas conversas. Só aparece para quem tem `menu.manageAssistants` (administrador, RN-21). |
| D2 | Confirmação **digitando o nome** do assistente: o botão "Excluir assistente" só habilita quando o texto digitado, sem espaços nas pontas, é igual ao nome. Conversa confirma só com o botão. |
| D3 | Com **reindexação em andamento**, a exclusão é recusada com 409 (`code: reindex_in_progress`) e mensagem pedindo para aguardar, como na exclusão de documento (SPEC-005). |

## Regras de negócio

- RN-44: excluir um assistente remove, nesta ordem: a collection física vigente no Qdrant (a que o alias `assistant-{id}` resolve, ou a de nome igual ao alias em bases antigas); os originais dos documentos; o registro do assistente, com tudo que depende dele em cascata. Se uma etapa falhar, o assistente continua listado e a exclusão pode ser repetida. Falha ao apagar um original é registrada em log e não interrompe a exclusão (o arquivo órfão não afeta buscas).
- RN-45: exclusão de assistente com reindexação em andamento é recusada (D3); nada é apagado.
- RN-46: só o administrador exclui assistente (RN-21); negativa auditada. A exclusão gera `assistant.deleted` com `assistant_id`, `name`, `collection` e `documents_removed`.

## Requisitos funcionais

- RF-96: o administrador exclui um assistente pela barra lateral (D1).
- RF-97: antes de excluir o assistente, o sistema mostra um modal informando que a base vetorial, os documentos e as conversas do assistente também serão excluídos, que a ação não pode ser desfeita, e pede o nome do assistente (D2). Cancelar, `Esc` ou clicar fora fecham sem excluir.
- RF-98: excluir conversa usa o mesmo componente de modal, no lugar de `window.confirm`.
- RF-99: enquanto a exclusão está em curso o modal mostra "Excluindo…" e não pode ser fechado; em caso de erro (409, 404, rede) o modal continua aberto e mostra a mensagem; em caso de sucesso fecha.

## Critérios de aceite

```gherkin
Cenário: excluir assistente com base vetorial (RF-96, RF-97, RN-44)
  Dado o administrador na barra lateral e o assistente "Jurídico" com documentos indexados
  Quando aciona a lixeira de "Jurídico"
  Então vê o aviso de que a base vetorial e os documentos também serão excluídos
  E o botão "Excluir assistente" fica desabilitado até digitar "Jurídico"
  Quando digita "Jurídico" e confirma
  Então a collection do assistente não existe mais no Qdrant
  E os originais dos documentos não existem mais no volume
  E o assistente some da lista e o evento "assistant.deleted" é auditado

Cenário: cancelar (RF-97)
  Quando abre o modal e cancela, pressiona Esc ou clica fora
  Então nada é excluído

Cenário: reindexação em andamento (RN-45)
  Dado uma reindexação em andamento no assistente
  Quando o administrador confirma a exclusão
  Então recebe 409 com a mensagem para aguardar a reindexação
  E o modal continua aberto com a mensagem; collection, arquivos e registro permanecem

Cenário: quem não é administrador (RN-46)
  Então não vê a lixeira na barra lateral
  E o DELETE responde 403 e a negativa é auditada

Cenário: excluir conversa (RF-98)
  Quando aciona a lixeira de uma conversa
  Então vê o modal padrão "Excluir conversa?" e não o diálogo do navegador
```

## Design da solução

- **Backend** (`application/use_cases/manage_assistant_access.py`): `DeleteAssistantUseCase`
  recebe também `DocumentRepository`, `DocumentFileStorage` e `ReindexJobRepository` (portas
  existentes). Fluxo: `require_admin` → busca o assistente (404) → `get_running` (409) → lista os
  documentos → apaga a collection resolvida → apaga os originais → apaga o registro → audita.
  A rota traduz `ReindexInProgressError` em 409 com `{code, message}`.
- **Frontend**: `shared/dialogs/confirm-dialog.component.ts` (standalone) com entradas `title`,
  `message`, `warning`, `confirmLabel`, `busyLabel`, `busy`, `error`, `requireText`, `tone` e
  saídas `confirmed` e `cancelled`; `role="alertdialog"`, `aria-modal`, foco preso com
  `cdkTrapFocus` (CDK já instalado) e devolvido ao fechar, `Esc` e clique no fundo fecham fora de
  `busy`. Visual igual ao modal "Criar assistente" (`rounded-3xl border-slate-800 bg-slate-900`,
  botões em pílula, aviso em âmbar como os avisos da tela de assistentes, botão destrutivo em
  `rose-600`). Regras puras em `shared/dialogs/confirm-dialog.ts` (comparação do nome, quando o
  diálogo fecha). O `ShellComponent` guarda o pedido pendente e fecha o modal quando o
  `loading` correspondente volta a `false` sem erro.

## Impacto arquitetural

Nenhuma porta, tabela, migração ou dependência nova. O domínio não muda.

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-113 | RN-44: apaga collection resolvida, originais e registro; auditoria com contagem | Unitário |
| CT-114 | RN-45: reindexação em andamento → `ReindexInProgressError`; nada apagado | Unitário |
| CT-115 | RN-44: falha ao apagar a collection mantém o assistente; falha ao apagar original não interrompe | Unitário |
| CT-116 | RN-46: não administrador recusado e auditado; assistente inexistente → não encontrado | Unitário |
| CT-117 | Regras do modal (nome digitado, fechamento só fora de `busy`, fecha após sucesso) | Vitest |
| CT-118 | Fluxo na pilha: assistente com documento indexado excluído pela barra lateral; collection e arquivo ausentes | Manual (Docker) |
| CT-119 | `DELETE /assistants/{id}`: 204 com a collection apagada, 409 com reindexação em andamento, 404 para assistente inexistente | Integração (container) |

## Riscos

- **Ingestão em curso.** Se o worker reservar um job e o assistente for excluído antes de ele
  criar a primeira collection, pode sobrar uma collection vazia sem assistente. A janela é de
  milissegundos e só existe quando o assistente ainda não tinha collection. Não há dano a buscas;
  limpeza manual se ocorrer.
- **Parâmetros do BM25** gravados por collection em `app_settings` ficam sem uso após a exclusão.
  Não afetam nada; ids de assistente não se repetem.
