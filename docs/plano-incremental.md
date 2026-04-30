# Plano Incremental

## 1. Fundação Documental

Objetivo: deixar visão, escopo, arquitetura e decisões principais compreensíveis antes do código.

Entregáveis:

- documentação de negócio
- documentação de arquitetura
- ADRs iniciais
- documentação de infraestrutura local
- estrutura base de pastas

Validação:

- revisar se o MVP está claro
- confirmar que decisões técnicas têm justificativa
- garantir que próximos passos são pequenos e testáveis

## 2. Ambiente Docker Mínimo

Objetivo: criar o `compose.yaml` com serviços base.

Entregáveis:

- `compose.yaml`
- Dockerfile do backend
- Dockerfile do frontend
- PostgreSQL com volume
- Qdrant com volume
- `.env.example`

Validação:

- `docker compose up --build`
- healthcheck da API
- Qdrant acessível
- PostgreSQL acessível

## 3. Fundação do Domínio Backend

Objetivo: modelar o núcleo sem depender de infraestrutura.

Entregáveis:

- entidades de assistente, documento, conversa e mensagem
- value objects principais
- interfaces de repositório, vector store, embeddings e LLM
- casos de uso puros iniciais

Validação:

- testes unitários sem Docker
- cobertura dos invariantes do domínio

## 4. Persistência e Assistentes

Objetivo: persistir assistentes e histórico.

Entregáveis:

- models e migrations
- repositórios PostgreSQL
- rotas de assistentes
- rotas de conversas

Validação:

- testes de integração com PostgreSQL em Docker
- criação e consulta de assistentes
- retomada de conversa

## 5. Ingestão e RAG

Objetivo: indexar documentos e recuperar contexto por assistente.

Entregáveis:

- upload de documentos
- extração de texto
- chunking
- embeddings locais
- gravação em Qdrant
- busca semântica isolada por collection

Validação:

- dois assistentes com documentos distintos
- busca sem mistura entre collections
- metadados mínimos por chunk

## 6. Fluxo Conversacional

Objetivo: conectar recuperação, avaliação e resposta.

Entregáveis:

- grafo LangGraph
- adapter de LLM configurável
- fallback para contexto insuficiente
- persistência de pergunta e resposta

Validação:

- testes com LLM fake
- resposta baseada em contexto recuperado
- fallback quando não há evidência

## 7. Frontend Angular

Objetivo: entregar a experiência mínima de uso.

Entregáveis:

- layout base
- seleção e criação de assistentes
- upload de documentos
- chat com Markdown
- store NgRx para estado principal

Validação:

- testes de componentes/store
- fluxo manual no Docker

## 8. Integração E2E do MVP

Objetivo: provar o ciclo completo.

Entregáveis:

- integração frontend-backend
- documentação de execução
- ajustes de UX e erros comuns

Validação:

- criar assistente
- enviar documento
- perguntar sobre o documento
- receber resposta baseada no conteúdo
- reiniciar ambiente e retomar histórico
