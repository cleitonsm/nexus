# SPEC-010 — Navegação da barra lateral e menu de Administração

**ID**: SPEC-20261025-010
**Status**: **Aprovada** em 2026-10-25 — decisões D1 a D9 escolhidas pelo autor; código entregue em 2026-10-25, validação no Docker e e2e pendentes (depende de `npm install @angular/cdk@^20.2`).
**Origem**: melhoria de usabilidade pedida pelo autor (exemplo: menu suspenso de configurações do Gemini); [planejamento](https://claude.ai/artifact/LKrPWKKXGHkoxuErBQroTv)
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

O rodapé da barra lateral empilha até sete itens soltos: "Conversas", cinco telas
administrativas e "Configurações", que abre o modal do LLM (SPEC-008). A lista cresce a cada
tela nova e mistura uso diário com administração.

O botão "Conversas" existe para compensar uma falha de navegação. Selecionar um assistente, uma
conversa recente ou "Nova conversa" muda o estado do store, mas não a rota. Em Auditoria, por
exemplo, clicar num assistente troca a lista de recentes e a tela continua em Auditoria.

Hoje, ao selecionar um assistente, o chat reabre a última conversa escolhida ou a mais recente
(`selectAssistant` e `loadAssistantConversationsSuccess` em `nexus.reducer.ts`).

A rota `/admin` (`AdminPageComponent`) não tem nenhum link e duplica o modal da chave do LLM.

## Decisões

| # | Escolha |
|---|---------|
| D1 | A barra lateral passa a ter, nesta ordem: **Assistentes**, **Recentes**, botão **Administração** e, no rodapé, os dados da conta e **Sair**, onde estão hoje. |
| D2 | **Administração** abre um menu suspenso com as telas permitidas ao papel (tabela abaixo). Sem nenhum item permitido (usuário comum), o botão não aparece. |
| D3 | O item **Configuração do LLM** abre o modal atual da SPEC-008. O título do modal deixa de ser "Administração" e passa a ser "Configuração do LLM". |
| D4 | O link **Conversas** é removido. Selecionar um assistente (inclusive o já ativo), uma conversa recente ou "Nova conversa" leva a `/chat`, a partir de qualquer tela. |
| D5 | Selecionar um assistente abre o **chat em branco**, com as conversas recentes dele carregadas na barra lateral. Nenhuma conversa é reaberta automaticamente. A primeira pergunta cria a conversa, como hoje. |
| D6 | A rota `/admin`, o `AdminPageComponent` e a entrada correspondente do e2e são removidos. |
| D7 | Os rótulos das telas não mudam: "Documentos e permissões", "Auditoria", "Conversas arquivadas", "Avaliações", "Consumo e limites". |
| D8 | Assistente e conversa na URL (`/chat/:assistantId/:conversationId`) ficam **fora do escopo** (ver Próximos passos). |
| D9 | O menu usa o **CDK Menu** (`@angular/cdk/menu`, versão alinhada ao Angular 20), que já entrega teclado, foco e fechamento por Esc e clique fora. É a única dependência nova. |

### Itens do menu por papel

| Item | Rota ou ação | Admin | Curador | Usuário |
|------|--------------|-------|---------|---------|
| Documentos e permissões | `/assistants` | Sim | Sim | Não |
| Auditoria | `/admin/audit` | Sim | Não | Não |
| Conversas arquivadas | `/admin/archived` | Sim | Não | Não |
| Avaliações | `/feedback` | Sim | Sim | Não |
| Consumo e limites | `/admin/usage` | Sim | Não | Não |
| Configuração do LLM | modal (SPEC-008) | Sim | Não | Não |

A visibilidade continua derivada de `menuFor()` (RF-46, RN-21). Os guards das rotas e a API
continuam verificando o papel: o menu é conveniência, não barreira (RNF-23).

## Requisitos funcionais

- RF-75: a barra lateral apresenta Assistentes, Recentes, Administração e, no rodapé, dados da conta e Sair (D1); não existe mais o link Conversas (D4).
- RF-76: o menu Administração lista só os itens permitidos ao papel do usuário, na ordem da tabela; o botão fica oculto quando a lista é vazia (D2, D3).
- RF-77: selecionar um assistente, uma conversa recente ou "Nova conversa" leva ao chat a partir de qualquer tela; selecionar um assistente abre o chat sem conversa aberta e carrega suas recentes (D4, D5).
- RF-78: o menu Administração é operável por teclado e leitor de tela: abre e fecha pelo botão, fecha com Esc, clique fora ou escolha de item, navega com as setas e devolve o foco ao botão ao fechar.

## Requisitos não funcionais

- Única dependência nova no frontend: `@angular/cdk` (D9).
- Sem mudança no backend, no domínio, nas rotas da API nem no banco.

## Critérios de aceite

```gherkin
Cenário: menu do administrador (RF-76)
  Dado um usuário com o papel admin
  Quando ele abre o menu Administração
  Então vê, nesta ordem, Documentos e permissões, Auditoria, Conversas arquivadas, Avaliações, Consumo e limites e Configuração do LLM

Cenário: menu do curador (RF-76)
  Dado um usuário com o papel curador
  Quando ele abre o menu Administração
  Então vê apenas Documentos e permissões e Avaliações

Cenário: usuário comum (RF-75, RF-76)
  Dado um usuário sem papel de admin nem de curador
  Então a barra lateral mostra Assistentes, Recentes, os dados da conta e Sair
  E não mostra o botão Administração nem o link Conversas

Cenário: configuração do LLM pelo menu (D3)
  Dado um administrador com o menu Administração aberto
  Quando ele escolhe Configuração do LLM
  Então o menu fecha e abre o modal com o título "Configuração do LLM"

Cenário: voltar ao chat pelo assistente (RF-77)
  Dado um administrador na tela de Auditoria
  Quando ele seleciona um assistente
  Então a tela passa a ser o chat, sem conversa aberta
  E as conversas recentes desse assistente aparecem na barra lateral

Cenário: assistente já ativo (RF-77)
  Dado um curador na tela de Avaliações com o assistente "Jurídico" ativo
  Quando ele seleciona "Jurídico"
  Então a tela passa a ser o chat

Cenário: conversa recente e nova conversa (RF-77)
  Dado um administrador na tela de Consumo e limites
  Quando ele seleciona uma conversa recente
  Então o chat abre essa conversa
  E, se em vez disso ele escolhe "Nova conversa", o chat abre a conversa criada

Cenário: teclado (RF-78)
  Dado o foco no botão Administração
  Quando o usuário pressiona Enter, desce com a seta e pressiona Esc
  Então o menu abre, o foco percorre os itens e, ao fechar, volta ao botão

Cenário: rota removida (D6)
  Quando um administrador acessa /admin
  Então é levado ao chat
```

## Design da solução

**Itens do menu.** Nova função pura `administrationMenu(menu: MenuVisibility)` em
`core/auth/access.ts`. Ela devolve a lista ordenada de itens visíveis, cada um com rótulo, ícone
e destino (`{ kind: "route", path }` ou `{ kind: "llmSettings" }`). `MenuVisibility` não muda. O
template só percorre a lista, e a regra fica testável sem Angular, como `resolveNavigation`.

**Componente do menu.** O botão Administração (`cdkMenuTriggerFor`) e o painel (`cdkMenu`, itens `cdkMenuItem`) ficam no `shell`:

- **Posição:** o painel abre para cima, ancorado no botão. Com a barra lateral recolhida
  (`lg:w-20`), abre à direita do ícone.
- **Acessibilidade:** papéis ARIA, setas, Esc, clique fora e devolução do foco vêm do CDK Menu.
  O painel é posicionado pelo overlay do CDK (`cdkMenuPosition`).
- **Barra lateral:** no celular, escolher um item também fecha a barra lateral.
- **Estado ativo:** o botão fica destacado quando a rota atual é uma das rotas do menu. Isso
  substitui o `routerLinkActive` dos links removidos.

**Navegação para o chat.** Novo efeito funcional em `nexus.effects.ts`
(`navigateToChatEffect`, `dispatch: false`). Ele escuta `selectAssistant`, `selectConversation`
e `createConversationSuccess` e chama `router.navigateByUrl("/chat")` quando a URL atual não
começa por `/chat`. Fica no efeito, e não no componente, para valer também quando a ação vem de
outro fluxo (por exemplo, `inferAssistantAndSend`).

**Chat em branco (D5).** No reducer:

- `selectAssistant` passa a definir `currentConversationId: null`.
- `loadAssistantConversationsSuccess` só atualiza a lista de recentes e não altera a conversa
  atual. Assim, uma lista que chega depois de uma conversa recém-criada (por exemplo, na
  inferência do assistente) não a fecha.
- `selectedConversationByAssistant` deixa de ser lido na seleção do assistente. Ele continua
  existindo enquanto outras ações o usarem.

**Remoções.**

- **No rodapé:** o link Conversas, os cinco links soltos e o botão Configurações.
- **Rota `/admin`:** a rota, `admin-page.component.ts`, `admin-page.component.html` e
  `"/admin"` em `ADMIN_ROUTES` de `e2e/access.spec.ts`. As rotas `admin/*` continuam.
- **No modal:** o título passa a ser "Configuração do LLM", e os ids `admin-api-key-title` e
  `aria-labelledby` são renomeados de acordo.

## Impacto arquitetural

Somente frontend: `core/auth/access.ts`, `shell/`, `store/nexus.effects.ts`,
`store/nexus.reducer.ts`, `app.routes.ts` e `pages/admin-page.*` (removido). Não há impacto no
domínio, nos casos de uso, na API, nas migrações, no Qdrant nem na `AccessPolicy`. Nenhuma ADR
nova.

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-78 | `administrationMenu` devolve 6 itens ordenados para admin, 2 para curador e lista vazia para usuário e para sessão sem usuário | Vitest |
| CT-79 | Reducer: `selectAssistant` zera a conversa atual; `loadAssistantConversationsSuccess` atualiza as recentes sem abrir nem trocar a conversa atual | Vitest |
| CT-80 | `navigateToChatEffect` navega para `/chat` nas três ações quando a URL é outra e não navega quando já está em `/chat` | Vitest |
| CT-81 | Barra lateral por papel: admin vê Administração com 6 itens, curador com 2, usuário sem o botão; ninguém vê o link Conversas | E2E (Playwright) |
| CT-82 | Em Auditoria, selecionar um assistente leva ao chat sem conversa aberta e com as recentes listadas | E2E (Playwright) |
| CT-83 | Teclado: Enter abre, setas percorrem, Esc fecha e o foco volta ao botão; clique fora fecha | E2E (Playwright) |
| CT-84 | `/admin` redireciona para o chat (atualiza `access.spec.ts`) | E2E (Playwright) |

## Riscos e dependências

- **Mudança de hábito (D5):** quem esperava reabrir a última conversa ao trocar de assistente
  passa a ver o chat vazio. A conversa continua um clique adiante, em Recentes.
- **Pontos que dependem do auto-abrir:** algum fluxo pode depender de a conversa reabrir sozinha
  (por exemplo, depois de excluir a conversa atual). O CT-79 e a suíte e2e existente cobrem isso;
  qualquer dependência encontrada é registrada aqui antes da correção.
- **Painel com a barra recolhida:** com a barra recolhida, o painel pode ultrapassar a borda da
  tela em alturas pequenas. A verificação é visual, na campanha.

## Decisões pendentes

Nenhuma. A DP1 (menu à mão ou CDK) foi decidida como D9.

## Próximos passos (fora do escopo)

- Assistente e conversa na URL (`/chat/:assistantId/:conversationId`), para a conversa
  sobreviver ao recarregamento da página e poder ser compartilhada por link (D8).

## Entrega (2026-10-25)

| Item | Situação |
|------|----------|
| CT-78 a CT-80 | 12 testes Vitest novos; suíte com 160 testes verdes |
| CT-81 a CT-84 | `frontend/e2e/navigation.spec.ts` e `access.spec.ts` atualizado; escritos, não executados (Playwright não instalado) |
| Build | Pendente: `npm install @angular/cdk@^20.2` em `frontend` (registro npm inacessível no ambiente de implementação); atualiza `package.json` e `package-lock.json` |
| Comportamento mantido | Excluir a conversa atual ainda abre a próxima conversa restante (`deleteConversationSuccess`), fora do escopo desta SPEC |
