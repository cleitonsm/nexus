# Frontend Angular e NgRx

## Objetivo

O frontend deve oferecer uma experiência simples para gerenciar assistentes, documentos e chat.
A arquitetura inicial deve ser previsível sem criar camadas excessivas para o MVP.

## Estrutura de Rotas e Shell

- O `AppComponent` atua como shell com sidebar persistente e `router-outlet`.
- Rotas de primeiro nivel:
  - `/chat`: experiencia conversacional isolada.
  - `/assistants`: criacao/listagem de assistentes e upload de documentos.
  - `/admin`: configuracao da API key global do sistema.
- `core`: servicos singleton, interceptors, configuracao e integracao HTTP.
- `shared`: componentes e utilitarios reutilizaveis.
- `features/chat`: conversa com mensagens em bolhas, input ancorado e renderizacao Markdown.
- `features/assistants`: administracao funcional de assistentes e documentos.
- `features/admin`: estado administrativo da API key (status e gravacao sem leitura).
- `store`: estado global NgRx por dominio (chat, assistants, admin e carregamentos/erro).

## Estado Global (Evolução MVP)

- assistente selecionado e lista de assistentes
- lista de conversas por assistente
- conversa ativa e mensagens da conversa selecionada
- status da API key global (`configurada`/`nao configurada`)
- estado de gravacao/substituicao da API key global
- documentos do assistente e estados de carregamento/erro

## Diretriz

Componentes devem concentrar apresentação e interação. Chamadas HTTP, normalização de estado e
efeitos assíncronos devem ficar em services, effects e stores.
