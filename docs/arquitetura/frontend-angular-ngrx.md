# Frontend Angular e NgRx

## Objetivo

O frontend deve oferecer uma experiência simples para gerenciar assistentes, documentos e chat.
A arquitetura inicial deve ser previsível sem criar camadas excessivas para o MVP.

## Estrutura de Rotas e Shell

- O `AppComponent` atua como shell com sidebar persistente e `router-outlet`.
- Rotas de primeiro nivel:
  - `/chat`: experiencia conversacional isolada.
  - `/assistants`: criacao/listagem de assistentes e upload de documentos.
  - `/admin/llm-credentials`: credenciais de LLM (SPEC-013; substituiu a API key global da
    SPEC-008).
- `core`: servicos singleton, interceptors, configuracao e integracao HTTP.
- `shared`: componentes e utilitarios reutilizaveis.
- `features/chat`: conversa com mensagens em bolhas, input ancorado e renderizacao Markdown.
- `features/assistants`: administracao funcional de assistentes e documentos.
- `features/assistants`: tambem as secoes "Modelo de linguagem" e "Recuperacao" do assistente
  (SPEC-013).
- `features/home` e `shared/home`: modal e regras do acesso rapido da tela inicial (SPEC-016).
- `features/assistants/assistant-profile-settings.component.ts` e `shared/assistants`: card
  "Dados do assistente" e regras puras de nome, descricao e prompt (limites, normalizacao,
  diferenca, nome repetido, quem ve o card e erro por `code`) (SPEC-017).
- `store`: estado global NgRx por dominio (chat, assistants, admin e carregamentos/erro).

## Estado Global (Evolução MVP)

- assistente selecionado e lista de assistentes
- lista de conversas por assistente
- conversa ativa e mensagens da conversa selecionada
- credenciais de LLM, padrao, impacto de troca da padrao e configuracao de LLM e recuperacao
  por assistente (fatia `llmConfig`, SPEC-013; nenhuma chave volta da API, so `key_configured`)
- acesso rapido da tela inicial (`homeAssistants`: ids, padrao, limite e se o usuario ja
  personalizou) e estado do modal de personalizacao (SPEC-016); o padrao vira o assistente
  ativo por `applyDefaultAssistant`, sem navegacao
- edicao do assistente (SPEC-017): `updateAssistant` com `exhaustMap`; o sucesso troca o item na
  lista de assistentes, o que atualiza barra lateral, cartoes e modal pelos seletores existentes
- documentos do assistente e estados de carregamento/erro

## Diretriz

Componentes devem concentrar apresentação e interação. Chamadas HTTP, normalização de estado e
efeitos assíncronos devem ficar em services, effects e stores.

## Evolução RAG Enterprise

Conteúdo **planejado**; as seções acima continuam descrevendo o frontend do MVP.

### Rotas e Acesso

- Todas as rotas passam a exigir sessão autenticada pelo Keycloak.
- `/chat`: qualquer usuário autenticado, restrito aos assistentes dos seus grupos.
- `/assistants`: curadores e administradores; gestão de documentos com estado, exclusão,
  substituição e restrição por grupo.
- `/assistants`: também mostra o painel "Índice de busca" (estado do índice, aviso de mudança do
  BM25 e botão de reindexar, PC-D2) e escolhe grupos do Keycloak num seletor (PC-D6).
- `/admin/llm-credentials`, `/admin/audit`, `/admin/usage` e `/admin/archived`: administradores;
  credenciais de LLM (SPEC-013), auditoria, consumo e conversas anteriores à autenticação (PC-D5).
- `/feedback`: curadores e administradores; avaliações negativas.
- Guards de rota por papel; itens de menu ocultos quando o papel não permite.

### Estado Global (acréscimos)

- sessão: usuário, papéis, grupos e situação da autenticação
- documentos com estado de ingestão, versão e motivo de falha
- citações e feedback por mensagem
- resposta em andamento durante o streaming
- avisos de limite de uso e de acesso negado

### Integração

- Serviço OIDC em `core/services`, com Authorization Code e PKCE; tokens mantidos em memória.
- Interceptor HTTP anexa o token e trata 401, 403 e 429.
- O estado de ingestão é atualizado por consulta periódica enquanto houver documentos em processamento.
- O chat consome a rota de streaming e exibe as fontes ao final da resposta.

### Diretriz

Permanece: componentes apresentam e despacham actions; autenticação, HTTP e streaming ficam em
services e effects. O frontend nunca é a única barreira de acesso (RNF-23).
