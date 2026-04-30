# Frontend Angular e NgRx

## Objetivo

O frontend deve oferecer uma experiência simples para gerenciar assistentes, documentos e chat.
A arquitetura inicial deve ser previsível sem criar camadas excessivas para o MVP.

## Estrutura

- `core`: serviços singleton, interceptors, configuração e integração HTTP.
- `shared`: componentes e utilitários reutilizáveis.
- `features/assistants`: listagem, criação e seleção de assistentes.
- `features/documents`: upload e status de documentos.
- `features/chat`: conversa, renderização Markdown e envio de mensagens.
- `store`: estado global com NgRx para assistente ativo, mensagens e documentos.

## Estado Global Inicial

- assistente selecionado
- lista de assistentes
- conversa ativa
- mensagens da conversa
- documentos do assistente
- estados de carregamento e erro

## Diretriz

Componentes devem concentrar apresentação e interação. Chamadas HTTP, normalização de estado e
efeitos assíncronos devem ficar em services, effects e stores.
