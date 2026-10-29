# SPEC-017 — Edição de nome, descrição e prompt do assistente

**ID**: SPEC-20261029-017
**Status**: **Implementada** em 2026-10-29 — CT-131 a CT-137 aprovados (unitários, integração no container e no PostgreSQL 16, Vitest e Playwright 5/5); CT-138 manual pendente. Histórico: **Aprovada** em 2026-10-29. O autor (Cleiton Medeiros) escolheu D1 = **administrador e curador** e seguiu a recomendação em D2 a D8.
**Origem**: pedido do autor (2026-10-29): "melhoria na qual seja possível editar o prompt, nome e
descrição dos assistentes".
**Plano**: [SPEC-017-plano-de-implementacao.md](SPEC-017-plano-de-implementacao.md)
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. Nome, descrição e prompt inicial só são definidos na criação (modal "Criar assistente" da barra
   lateral, `POST /assistants`, `CreateAssistantUseCase`). Depois disso não há rota, caso de uso nem
   tela para alterá-los. Para corrigir um erro de digitação ou ajustar o comportamento do assistente,
   hoje é preciso excluí-lo (SPEC-014), o que apaga a base vetorial, e recriá-lo do zero.
2. O suporte técnico já existe em parte:
   - a entidade `Assistant` (`domain/entities.py`) valida descrição e prompt não vazios, e o
     `AssistantName` (`domain/value_objects.py`) limita o nome a 80 caracteres;
   - as colunas `assistants.name` (`varchar(80)`), `description` (`text`) e `initial_prompt` (`text`)
     já existem (migração `0001`). **Não é preciso migração**;
   - `PostgresAssistantRepository.save` já altera os três campos de um assistente existente. Porém,
     se o assistente foi excluído entre a leitura e a gravação, esse método o **recria** sem grupos;
   - o chat lê o assistente a cada pergunta (`chat_with_assistant.py`, `assistant_initial_prompt`).
     Por isso um prompt alterado vale a partir da próxima pergunta, sem reiniciar nada.
3. O prompt do assistente é a parte inicial da instrução de sistema. `build_answer_instruction`
   (`application/services/grounded_answer.py`) sempre acrescenta as regras de formato e de citação.
   Sem prompt, vale o `DEFAULT_ANSWER_INSTRUCTION`. Assim, editar o prompt não desliga a citação `[n]`
   nem o fallback sem LLM (RN da SPEC-003).
4. O nome e a descrição entram no catálogo da inferência de assistente (`infer_assistant.py`), que
   também recebe o prompt. Editar esses campos muda a escolha automática.
5. Achado: `GET /assistants` devolve `initial_prompt` a **qualquer** usuário que veja o assistente,
   mas o frontend não exibe esse campo fora da criação. A D5 decide se isso continua.

## Decisões

Escolhas registradas em 2026-10-29 pelo autor na coluna **Escolha**. D1 contraria a recomendação inicial; as demais a seguem.

| # | Questão | Opções | Recomendação | Escolha (2026-10-29) |
|---|---------|--------|--------------|----------------------|
| D1 | **Quem edita** | Só o administrador (`nexus-admin`), como na criação (RN-21); administrador e curador dos assistentes que cura | **Só o administrador**. O prompt muda o comportamento para todos os usuários do assistente, e a criação já é exclusiva dele. O curador continua cuidando só da base | **Administrador e curador**. O curador edita só os assistentes cuja base cura, pela mesma regra de `AccessPolicy.can_manage_documents` (pertence a um dos grupos do assistente). Assistente sem grupo continua só do administrador |
| D2 | **Onde se edita** | Card "Dados do assistente" no topo da página `/assistants`, junto das configurações de LLM e de recuperação (SPEC-013); modal de criação reaproveitado, aberto por um ícone de lápis na barra lateral | **Card na página `/assistants`**: é lá que fica a configuração por assistente, e a barra lateral de 72 px (SPEC-015) já tem pouco espaço para ação | Card em `/assistants` |
| D3 | **Limite de tamanho** de descrição e prompt (hoje sem limite; o nome tem 80) | Descrição 500 e prompt 4000 caracteres; descrição 1000 e prompt 8000; sem limite | **500 e 4000**. 4000 caracteres são cerca de 1000 tokens, o que deixa folga para os 2000 de contexto e os 1500 de histórico (SPEC-003). Uma descrição curta também melhora o catálogo da inferência. Vale para **criação e edição**. Antes, conferir se algum assistente gravado passa do limite (P0) | 500 e 4000 |
| D4 | **Apagar descrição ou prompt** | Permitir: campo vazio grava `null` (o prompt volta ao padrão do sistema); proibir apagar depois de preenchido | **Permitir**, com o aviso "Sem prompt, o assistente usa a instrução padrão do sistema" no formulário. Repete a regra da criação, em que vazio vira `null` | Permitir |
| D5 | **Quem lê o prompt** em `GET /assistants` | Manter para todos; devolver `initial_prompt` só a quem gerencia o assistente (administrador) e `null` aos demais | **Só ao administrador**. O prompt é configuração e ajuda quem tenta contornar as instruções. Nenhuma tela de usuário comum usa o campo. Impacto: muda a resposta de uma rota existente, então o CT-134 cobre esse caso | Só quem pode editar aquele assistente (D1): administrador e curador dele |
| D6 | **O que a auditoria guarda** | Texto completo antes e depois; campos alterados, nome antes e depois, e tamanho mais SHA-256 da descrição e do prompt; só os nomes dos campos alterados | **Campos alterados, nome antes e depois, tamanho e SHA-256 da descrição e do prompt**. Dá para provar o que mudou sem copiar texto livre para a trilha append-only. Histórico com restauração de versões fica para outra SPEC | Campos, nome e hash |
| D7 | **Edição concorrente** (dois administradores na mesma tela) | Última gravação vence; controle otimista com `updated_at` (nova migração `0013`) e 409 `assistant_changed` | **Última gravação vence**. Os administradores são poucos, e o evento de auditoria mostra quem gravou por último. O controle otimista fica registrado como evolução | Última gravação vence |
| D8 | **Nome repetido** entre assistentes (hoje permitido) | Manter permitido; exigir nome único sem diferenciar maiúsculas (índice novo e migração) | **Manter permitido** nesta SPEC. Um índice único pode falhar sobre dados existentes e muda a criação. O formulário avisa quando o nome já existe, sem bloquear | Permitido, com aviso |

## Requisitos funcionais

- RF-108: o administrador, ou o curador do assistente (D1), altera nome, descrição e prompt inicial de um assistente existente sem
  excluí-lo. Grupos, documentos, base vetorial, credencial, modelo, perfil de recuperação, conversas
  e acesso rápido (SPEC-016) continuam como estavam.
- RF-109: a alteração vale a partir da próxima pergunta, inclusive em conversa já aberta, e na
  inferência de assistente. As respostas já gravadas não mudam.
- RF-110: o card "Dados do assistente" (D2) mostra os valores atuais, os contadores de caracteres
  (D3), o aviso do prompt vazio (D4) e os botões "Salvar" e "Descartar". "Salvar" fica desabilitado
  sem alteração ou com campo inválido. Depois de salvar, o novo nome aparece na barra lateral, nos
  cartões da tela inicial e no modal de acesso rápido sem recarregar a página.
- RF-111: `GET /assistants` devolve `initial_prompt` só a quem pode editar aquele assistente
  (administrador ou curador dele) e `null` aos demais (D5).

## Regras de negócio

- RN-51: nome obrigatório, com no máximo 80 caracteres após remover os espaços das pontas. Descrição
  com no máximo `MAX_ASSISTANT_DESCRIPTION` e prompt com no máximo `MAX_ASSISTANT_PROMPT` caracteres
  (D3). Descrição e prompt vazios ou só com espaços gravam `null` (D4). Os mesmos limites valem na
  criação.
- RN-52: altera o administrador ou o curador que pertence a um dos grupos do assistente
  (`AccessPolicy.can_manage_documents`, D1). Assistente sem grupo é só do administrador. Usuário
  comum ou curador de outro assistente recebe 403, e a tentativa negada vai
  para a auditoria, como nas demais ações administrativas. Assistente inexistente recebe 404
  `assistant_not_found`.
- RN-53: a alteração gera o evento `assistant.updated` com `changed_fields`, o nome antes e depois e o
  tamanho e SHA-256 da descrição e do prompt, antes e depois (D6). Nenhum log, span ou evento leva o
  texto do prompt. Uma gravação sem alteração devolve 200 e não gera evento.
- RN-54: a alteração grava só as três colunas e não recria o assistente. Se ele foi excluído antes da
  gravação, a resposta é 404.

## Critérios de aceite

```gherkin
Cenário: editar os três campos (RF-108, RF-110)
  Dado o assistente "Assistente jurídico" com grupos e documentos indexados
  Quando o administrador muda o nome para "Jurídico e Contratos", a descrição e o prompt
  E clica em "Salvar"
  Então a barra lateral mostra "Jurídico e Contratos" sem recarregar
  E os grupos, os documentos e o índice de busca continuam iguais
  E a trilha de auditoria tem um evento "assistant.updated" sem o texto do prompt

Cenário: prompt novo na próxima pergunta (RF-109)
  Dado uma conversa aberta com o assistente
  Quando o administrador troca o prompt para pedir respostas em tópicos
  E o usuário envia uma nova pergunta na mesma conversa
  Então a instrução de sistema da nova resposta começa pelo prompt novo
  E ainda traz as regras de formato e de citação
  E as respostas anteriores da conversa não mudam

Cenário: apagar o prompt (D4)
  Quando o administrador apaga o prompt e salva
  Então o assistente passa a usar a instrução padrão do sistema

Cenário: limites (RN-51)
  Quando o prompt passa de 4000 caracteres
  Então o contador fica vermelho e "Salvar" desabilitado
  E a API responde 422 "assistant_prompt_too_long" a um PUT com esse prompt
  E responde 422 "assistant_name_required" a um nome só com espaços

Cenário: curador do assistente edita (RN-52, D1)
  Dado um curador do grupo "juridico", vinculado ao "Assistente jurídico"
  Quando ele altera o prompt do "Assistente jurídico"
  Então a API responde 200 e o evento registra o curador como autor

Cenário: sem permissão (RN-52)
  Quando um usuário comum, ou o curador de outro assistente, envia PUT /assistants/{id}
  Então a API responde 403
  E a tentativa negada fica na auditoria

Cenário: assistente excluído no meio (RN-54)
  Dado que outro administrador excluiu o assistente
  Quando o administrador salva a edição
  Então a API responde 404 "assistant_not_found"
  E o assistente não é recriado

Cenário: prompt oculto a quem não edita (RF-111, D5)
  Quando um usuário comum lista os assistentes
  Então "initial_prompt" vem null
  E o administrador e o curador do assistente recebem o texto do prompt
```

## Design da solução

### Domínio

- `domain/assistant_profile.py`: `MAX_ASSISTANT_NAME` (80), `MAX_ASSISTANT_DESCRIPTION` (500) e
  `MAX_ASSISTANT_PROMPT` (4000) (D3); `build_assistant_profile(name, description, prompt)` normaliza
  e valida, levantando `AssistantProfileValidationError` (subclasse de `DomainValidationError`) com
  `code` `assistant_name_required`, `assistant_name_too_long`, `assistant_description_too_long` ou
  `assistant_prompt_too_long`. Criação e edição usam essa função. Os limites **não** ficam em
  `Assistant.__post_init__`, para que a leitura de um assistente gravado antes deles nunca falhe.
- Função pura `normalize_optional_text(value) -> str | None` (vazio → `None`, D4).
- Função pura `assistant_profile_changes(before, after) -> tuple[str, ...]`, que devolve os campos
  alterados (RN-53).
- Porta `AssistantRepository.update_profile(assistant_id, *, name, description, initial_prompt) ->
  Assistant | None`, que grava só as três colunas e devolve `None` se o assistente não existe (RN-54).
  `save` continua só para a criação.
- `AuditAction.ASSISTANT_UPDATED = "assistant.updated"`.

### Aplicação (`application/use_cases/update_assistant.py`)

- `UpdateAssistantInput(user, assistant_id, name, description, initial_prompt)` (frozen).
- `UpdateAssistantUseCase.execute`:
  1. `access_control.require_assistant_edit(user, assistant_id, ASSISTANT_UPDATED)`, método novo
     que repete a regra de `require_document_management` (admin ou curador do assistente) e
     audita a negação (D1);
  2. `get_by_id` → `AssistantNotFoundError`;
  3. monta a entidade nova (RN-51);
  4. se não houver alteração, devolve o DTO atual;
  5. senão, `update_profile`, onde `None` vira `AssistantNotFoundError`;
  6. audita (D6, digest com `hashlib.sha256` no caso de uso) e devolve `AssistantDTO`.
- `AssistantDTO.from_entity(assistant, *, reveal_prompt: bool)` para a D5. `ListAssistantsUseCase`
  passa `reveal_prompt=AccessPolicy.can_manage_documents(user, groups)` por assistente (os grupos
  já vêm de `visible_assistants`).

### API (`api/routes/assistants.py`)

| Método | Rota | Corpo / resposta | Erros |
|--------|------|------------------|-------|
| PUT | `/assistants/{assistant_id}` | entrada `{name, description, initial_prompt}` (substitui os três); resposta `AssistantResponse` | 401; 403; 404 `assistant_not_found`; 422 com o `code` da RN-51 |

O schema `UpdateAssistantRequest` tem um teto de 20 000 caracteres por campo no Pydantic, só para
recusar cedo corpos enormes; fica acima dos limites para que o 422 traga o `code` da RN-51, que
continua no domínio. Os códigos novos ficam em
`api/error_codes.py`. A resposta 422 nunca ecoa o texto enviado.

### Frontend

- `nexus-api.service.ts`: `updateAssistant(id, body)`.
- Store `nexus`: actions `updateAssistant`, `updateAssistantSuccess` (troca o item em `assistants`,
  o que atualiza barra lateral, cartões e modal pelos seletores existentes) e `updateAssistantFailure`;
  effect com `exhaustMap`; `loading.updateAssistant`.
- Regras puras em `shared/assistants/assistant-profile.ts`: normalização, validação dos limites,
  diferença entre o formulário e o atual, e aviso de nome repetido (D8).
- Componente `features/assistants/assistant-profile-settings.component.ts`, com formulário reativo e
  contadores no padrão dos cards da SPEC-013. Fica no topo da página `/assistants`, visível ao administrador e ao
  curador do assistente: `canEditAssistantProfile` libera quem tem `manageAssistants`, ou
  `manageDocuments` com `groups` preenchido (a API só devolve os grupos a quem gerencia o
  assistente). A API continua sendo a guarda. "Descartar" volta aos valores atuais, e trocar de assistente com
  alteração não salva descarta sem perguntar. Esse último ponto pode virar decisão na revisão.

### Persistência

Nenhuma mudança de esquema. `PostgresAssistantRepository.update_profile` faz um `UPDATE ... WHERE
id = :id RETURNING *` e não chama `session.get` seguido de `add`.

## Impacto arquitetural

- Sem ADR nova: segue a ADR 0002 (camadas) e a ADR 0008 (papéis). A D1 amplia o papel `nexus-curador`:
  além da base, ele passa a configurar nome, descrição e prompt do assistente que cura. Registrar
  isso na matriz de permissões da SPEC-004.
- Sem migração. Se a D7 mudar para controle otimista, entra a migração `0013` pelo `/new-migration`.
- Sem efeito no Qdrant, na ingestão nem na avaliação. Uma mudança de prompt pode alterar a medida do
  `scripts/eval.*`. Por isso o plano recomenda rodar a avaliação do assistente piloto depois de editar
  o prompt dele.

## Estratégia de testes

| ID | Tipo | O que cobre | Requisitos |
|----|------|-------------|------------|
| CT-131 | Unitário | Entidade e funções puras: limites com 0, 1, máximo e máximo + 1; vazio → `None`; `code` de cada erro; `assistant_profile_changes` | RN-51, D3, D4 |
| CT-132 | Unitário | `UpdateAssistantUseCase` com dublês: administrador e curador do assistente alteram; usuário comum e curador de outro assistente → negado e auditado; assistente sem grupo → só admin; inexistente e excluído no meio (`update_profile` → `None`) → not found sem recriar; sem alteração → sem evento; evento sem texto, com hash e tamanho; `reveal_prompt` na listagem | RF-108, RF-111, RN-52 a RN-54 |
| CT-133 | Unitário | `build_answer_instruction` com prompt editado: começa pelo prompt e sempre traz formato e citação; `None` → padrão | RF-109, D4 |
| CT-134 | Integração | `PUT /assistants/{id}`: 200, 401, 403, 404, 422 por `code`; grupos, documentos e LLM intactos; `GET /assistants` com prompt oculto ao usuário comum e visível ao curador do assistente | RF-108, RF-111, RN-51 a RN-54 |
| CT-135 | Integração (Docker) | `update_profile` no PostgreSQL 16: grava só as três colunas e não desfaz credencial e perfil gravados ao mesmo tempo; assistente inexistente → `None` sem linha nova | RN-54 |
| CT-136 | Vitest | Regras puras (contadores, diferença, nome repetido), reducer (`updateAssistantSuccess` troca o item), effect (sucesso e 422 com `code`), card ("Salvar" desabilitado sem alteração ou inválido; "Descartar") | RF-110 |
| CT-137 | E2E (Playwright) | Editar nome e prompt, ver o nome novo na barra lateral sem recarregar, recarregar e conferir; usuário comum não vê o card | RF-108, RF-110 |
| CT-138 | Manual (visual) | Card a 360 px e 1280 px, contadores, aviso do prompt vazio e foco por teclado | RF-110 |

## Riscos e dependências

| Risco | Mitigação |
|-------|-----------|
| O limite da D3 recusa assistentes já gravados com texto maior | P0 confere os tamanhos no banco local pelo MCP `postgres` (somente leitura) antes de aprovar. Se houver excedentes, o limite vale só na gravação, e a leitura não falha |
| Um prompt ruim degrada as respostas | As regras de formato e de citação continuam fixas (contexto 3), o evento de auditoria mostra quem mudou, e o plano recomenda a avaliação depois de editar |
| A D5 quebra um cliente que lia `initial_prompt` | Hoje só a criação usa o campo. O CT-134 cobre a mudança |
| Concorrência entre dois editores (D7) | Última gravação vence, com rastro na auditoria |
| Curador muda o prompt de forma indevida (D1) | Evento `assistant.updated` com o autor e o hash; o administrador revisa pela `/admin/audit` |

## Decisões pendentes

Nenhuma. D1 a D8 escolhidas em 2026-10-29.
