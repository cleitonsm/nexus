# SPEC-016 — Acesso rápido a assistentes na tela inicial

**ID**: SPEC-20261028-016
**Status**: **Implementada e validada** em 2026-10-29 — CT-124 a CT-130 aprovados (unitários, integração no PostgreSQL 16, Vitest, Playwright 4/4 e roteiro visual no Chrome). Histórico: **Implementada** em 2026-10-28 (confirmação do autor); **Aprovada** em 2026-10-28 — autor (Cleiton Medeiros) escolheu D1 = 4, D3, D5/D6 e D7 como recomendado; D2, D4 e D8 seguem a recomendação.
**Origem**: pedido do autor (2026-10-28): "permitir ao usuário escolher, dentre os assistentes
cadastrados, quais ficam disponíveis na tela inicial como acesso rápido. A tela pode ter até N
assistentes escolhidos, e o usuário deve marcar um deles como padrão, que sempre aparece marcado."
**Plano**: [SPEC-016-plano-de-implementacao.md](SPEC-016-plano-de-implementacao.md)
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. A tela inicial (`pages/chat-page.component.html`, bloco `assistantsCards`) mostra
   `assistants().slice(0, 3)`: os três primeiros da lista que a API devolve. O usuário não escolhe
   quais aparecem; quem tem acesso a muitos assistentes não vê os que mais usa.
2. Não existe assistente padrão. Ao abrir o Nexus, `activeAssistantId` é `null` e nenhum cartão
   aparece marcado; a primeira pergunta sem assistente cai na inferência (`inferAssistantAndSend`,
   `POST /assistants/infer`).
3. Não há preferência de usuário guardada no servidor. O único estado por usuário são as conversas
   (`conversations.owner_user_id`).

## Decisões

Escolhas registradas em 2026-10-28 pelo autor: **todas as recomendações**, com D1 = **4**.

| # | Questão | Opções | Recomendação |
|---|---------|--------|--------------|
| D1 | **Quantos assistentes** cabem no acesso rápido (o pedido não trouxe o número) | 3 (o layout de hoje); 4; 6 (duas linhas de 3) | **4**: cabe numa linha no desktop com cartões de 240 px (`w-60`) e dá folga sobre os 3 de hoje. Constante única no domínio (`MAX_HOME_ASSISTANTS`), sem variável de ambiente |
| D2 | Onde a escolha fica guardada | Servidor, por usuário (tabela nova); `localStorage` do navegador | **Servidor**: vale em qualquer navegador e máquina, e o projeto não guarda estado de usuário no navegador |
| D3 | Onde o usuário configura | Modal aberto na própria tela inicial; página nova `/preferences` | **Modal na tela inicial**, aberto pelo botão "Personalizar acesso rápido" abaixo dos cartões; sem rota nova |
| D4 | Usuário que nunca configurou | Mostrar os N primeiros visíveis com o primeiro como padrão; mostrar nada e convidar a configurar | **Os N primeiros visíveis, o primeiro como padrão** (comportamento de hoje, agora com padrão marcado). A resposta informa `customized: false` |
| D5 | O que "sempre aparece marcado" significa | O padrão vem selecionado (assistente ativo) ao abrir o Nexus e a cada "Nova conversa"; só um selo "Padrão" no cartão, sem selecionar | **Selecionado e com selo**: ao abrir o Nexus e em "Nova conversa", o padrão é o assistente ativo e o cartão aparece marcado (anel e ✓ de hoje) com o selo "Padrão". Clicar em outro cartão troca o ativo só naquela conversa |
| D6 | Inferência do assistente na tela inicial | Deixa de acontecer na tela inicial (sempre há um ativo); continua quando o usuário desmarca a seleção | **Deixa de acontecer na tela inicial** enquanto houver padrão. `POST /assistants/infer` e `inferAssistantAndSend` ficam para quem não tem assistente visível/padrão (nenhum efeito prático hoje). Impacto: fluxo de inferência da SPEC-010 passa a ser exceção |
| D7 | Ordem dos cartões | Padrão primeiro e os outros na ordem da lista de assistentes; ordem livre (arrastar) | **Padrão primeiro, os outros na ordem em que o usuário os marcou** (posição gravada). Sem arrastar nesta SPEC |
| D8 | Assistente escolhido que some (excluído, SPEC-014, ou o usuário perde o grupo) | Some do acesso rápido em silêncio; aviso ao usuário | **Some em silêncio na leitura**; se era o padrão, o primeiro que sobrou vira padrão efetivo; se nada sobrou, vale a D4. Exclusão apaga a linha por `ON DELETE CASCADE`; perda de grupo só filtra (a linha volta a valer se o acesso voltar) |

## Requisitos funcionais

- RF-103: o usuário escolhe, entre os assistentes que pode usar (RF-42), de 1 a `MAX_HOME_ASSISTANTS`
  (D1) para o acesso rápido da tela inicial, e exatamente um deles como padrão.
- RF-104: a tela inicial mostra só os assistentes do acesso rápido efetivo (RN-49), na ordem da D7,
  com o selo "Padrão" no padrão.
- RF-105: ao abrir o Nexus e a cada "Nova conversa", o assistente padrão é o ativo e o cartão dele
  aparece marcado (D5); a seleção de outro cartão não altera a preferência gravada.
- RF-106: a escolha fica gravada no servidor por usuário (D2) e vale em qualquer sessão; um usuário
  nunca lê nem altera a escolha de outro.
- RF-107: o modal "Personalizar acesso rápido" lista todos os assistentes visíveis, com marcação de
  acesso rápido e escolha do padrão; impede salvar acima do limite, sem nenhum marcado ou com
  padrão fora dos marcados, e mostra o contador "n de N".

## Regras de negócio

- RN-47: a seleção tem de 1 a `MAX_HOME_ASSISTANTS` assistentes, sem repetição, e o padrão é um deles.
- RN-48: só entra na seleção assistente que o usuário pode acessar no momento do envio
  (`AccessPolicy.can_access_assistant`); assistente inexistente ou sem acesso recebe a mesma
  resposta (422 `assistant_not_available`), sem revelar se existe.
- RN-49: acesso rápido efetivo = seleção gravada filtrada pelos assistentes visíveis agora, na ordem
  gravada; padrão efetivo = padrão gravado se continua visível, senão o primeiro que sobrou; seleção
  vazia depois do filtro ou nunca gravada → D4.
- RN-50: preferência de acesso rápido é configuração pessoal: não gera evento de auditoria
  (que é para ação administrativa e de curadoria); gera log `home_assistants.saved` só com id do
  usuário e quantidade.

## Critérios de aceite

```gherkin
Cenário: usuário sem preferência (RF-104, D4)
  Dado que o usuário pode usar 5 assistentes e nunca configurou o acesso rápido
  Quando abre o Nexus
  Então vê os 4 primeiros assistentes na tela inicial
  E o primeiro aparece marcado com o selo "Padrão"

Cenário: escolher acesso rápido e padrão (RF-103, RF-107)
  Dado o modal "Personalizar acesso rápido" aberto
  Quando marco "Assistente jurídico" e "Departamento Financeiro/Contábil"
  E escolho "Departamento Financeiro/Contábil" como padrão
  E salvo
  Então a tela inicial mostra "Departamento Financeiro/Contábil" primeiro, marcado e com o selo "Padrão"
  E em seguida "Assistente jurídico"

Cenário: limite de assistentes (RN-47)
  Dado 4 assistentes já marcados no modal
  Então os demais ficam desabilitados e o contador mostra "4 de 4"
  E a API responde 422 "home_assistants_limit" a um PUT com 5

Cenário: padrão sempre marcado (RF-105)
  Dado "Assistente jurídico" como padrão
  Quando seleciono outro cartão e depois clico em "Nova conversa"
  Então "Assistente jurídico" volta a ser o ativo e aparece marcado

Cenário: assistente sem acesso (RN-48)
  Quando envio um PUT com o id de um assistente fora dos meus grupos
  Então a API responde 422 "assistant_not_available"
  E a mesma resposta vem para um id inexistente

Cenário: padrão perde o acesso (RN-49, D8)
  Dado "Assistente jurídico" padrão e "Nexus Normativo" também no acesso rápido
  Quando o usuário sai do grupo do "Assistente jurídico"
  Então a tela inicial mostra só "Nexus Normativo", marcado como padrão

Cenário: escolha pessoal (RF-106)
  Dado que Ana salvou o seu acesso rápido
  Quando Bruno abre o Nexus
  Então Bruno vê o próprio acesso rápido, nunca o de Ana
```

## Design da solução

### Domínio (`domain/home_assistants.py`)

- `MAX_HOME_ASSISTANTS: Final = 4` (D1).
- `HomeAssistantSelection` (`dataclass(frozen=True, slots=True)`): `assistant_ids: tuple[AssistantId, ...]`
  (ordem da D7) e `default_id: AssistantId`; `__post_init__` aplica a RN-47 com
  `DomainValidationError` e os códigos `home_assistants_empty`, `home_assistants_limit`,
  `home_assistants_duplicate`, `home_assistants_default_not_selected`.
- `effective_home_assistants(saved: HomeAssistantSelection | None, visible: Sequence[AssistantId])
  -> EffectiveHomeAssistants | None` (RN-49 e D4); `None` só quando não há assistente visível.
- Porta `HomeAssistantPreferenceRepository(Protocol)`: `get(user_id) -> HomeAssistantSelection | None`
  e `replace(user_id, selection) -> None` (troca a seleção inteira numa transação).

### Aplicação (`application/use_cases/manage_home_assistants.py`)

- `GetHomeAssistantsUseCase.execute(user)` → `HomeAssistantsDTO(assistant_ids, default_id, max,
  customized)`; visíveis vêm de `AccessControl.visible_assistants`, como em `ListAssistantsUseCase`.
- `SetHomeAssistantsUseCase.execute(SetHomeAssistantsInput(user, assistant_ids, default_id))`:
  valida RN-48 com a `AccessPolicy` para cada id, monta a seleção (RN-47), grava e devolve o efetivo.

### API (`api/routes/me.py`)

| Método | Rota | Corpo / resposta | Erros |
|--------|------|------------------|-------|
| GET | `/me/home-assistants` | `{assistant_ids, default_assistant_id, max, customized}`; `default_assistant_id` `null` só sem assistente visível | 401 |
| PUT | `/me/home-assistants` | entrada `{assistant_ids, default_assistant_id}`; resposta igual ao GET | 401; 422 com os `code` da RN-47 e `assistant_not_available` (RN-48) |

O dono é sempre `user.id` do token; não há id de usuário na rota (RF-106). Códigos novos em
`api/error_codes.py`.

### Persistência

Migração nova `0012_user_home_assistants` (nenhuma existente é editada):

```text
user_home_assistants
  owner_user_id  varchar  NOT NULL     -- mesmo tipo de conversations.owner_user_id
  assistant_id   varchar(64) NOT NULL  FK assistants.id ON DELETE CASCADE (D8)
  position       smallint NOT NULL     -- ordem da D7
  is_default     boolean  NOT NULL DEFAULT false
  PRIMARY KEY (owner_user_id, assistant_id)
  UNIQUE INDEX ux_user_home_default ON (owner_user_id) WHERE is_default
```

`PostgresHomeAssistantPreferenceRepository.replace` apaga e insere as linhas do usuário na mesma
transação. O limite fica no domínio, não no banco (muda sem migração).

### Frontend

- Slice no store `nexus`: `homeAssistants: { ids, defaultId, max, customized, loaded }`; actions
  `loadHomeAssistants`, `saveHomeAssistants` e respectivos `Success`/`Failure`; effect carrega
  depois de `loadAssistantsSuccess` e recarrega depois de `deleteAssistantSuccess`; HTTP em
  `core/services/nexus-api.service.ts`.
- Action nova `applyDefaultAssistant` (D5): define `activeAssistantId` sem passar pelo
  `navigateToChatEffect`, para não tirar o usuário de uma tela administrativa ao carregar. É
  despachada no carregamento (se não há assistente ativo nem conversa aberta) e em "Nova conversa".
- Regras puras em `shared/home/home-assistants.ts` (alternar marcação respeitando o limite, escolher
  padrão, padrão automático quando o atual é desmarcado, ordem da D7, `canSave`), testadas no Vitest.
- `features/home/home-assistants-dialog.component.ts`: modal no padrão visual da SPEC-014
  (`shared/dialogs`), com lista de assistentes visíveis, caixa de seleção por linha, botão de rádio
  "Padrão" habilitado só nas linhas marcadas, contador "n de N", Salvar/Cancelar.
- `chat-page`: `topAssistants` passa a vir do seletor `selectHomeAssistants` (efetivo); cartão do
  padrão com selo "Padrão"; botão "Personalizar acesso rápido" abaixo dos cartões.

## Impacto arquitetural

- Tabela e migração novas (`0012`); porta e repositório novos; duas rotas sob `/me`. Nenhuma
  dependência nova, nenhuma mudança no Qdrant nem no pipeline RAG.
- O domínio só usa `AssistantId` e `DomainValidationError`.
- Comportamento visível muda: a tela inicial deixa de começar sem assistente (D5, D6).
- ADR nova não é necessária (preferência de usuário dentro do monólito, padrão já usado).

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-124 | `HomeAssistantSelection` (RN-47) e `effective_home_assistants` (RN-49, D4, D8) | Unitário (`unittest`) |
| CT-125 | Casos de uso: RN-48 com a `AccessPolicy`, dono = usuário do token, `customized` | Unitário com dublês (`access_doubles.py`) |
| CT-126 | Migração `0012` e repositório: troca atômica, índice do padrão único, cascata ao excluir assistente | Integração (Docker) |
| CT-127 | API: GET/PUT, códigos 422, isolamento entre dois usuários, inexistente = sem acesso | Integração (Docker) |
| CT-128 | Regras puras do modal, reducer e effects (`applyDefaultAssistant` não navega) | Vitest |
| CT-129 | E2E: personalizar, recarregar a página e ver o padrão marcado; "Nova conversa" volta ao padrão | E2E (Playwright) |
| CT-130 | Visual: cartões, selo "Padrão", modal e contador no desktop e no celular | Manual (navegador) |

## Riscos e dependências

- D6 muda o fluxo da inferência do assistente: quem hoje pergunta direto na tela inicial e conta com
  a inferência passa a perguntar ao padrão. Mitigação: selo "Padrão" visível e troca por um clique.
- Usuário com acesso a um só assistente: o modal mostra uma linha, já marcada e padrão.
- Depende da SPEC-014 (exclusão de assistente) para o `CASCADE` e do modal padrão.

## Decisões pendentes

Nenhuma. D1 a D8 escolhidas em 2026-10-28.
