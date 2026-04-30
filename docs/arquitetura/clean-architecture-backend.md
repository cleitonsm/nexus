# Clean Architecture no Backend

## Objetivo

Separar regras do produto de detalhes de framework, banco, busca vetorial e provedores de IA.
Isso permite testar o núcleo do sistema sem depender de Docker, Qdrant, PostgreSQL ou LLM real.

## Camadas

### Domain

Contém entidades, value objects e interfaces estáveis:

- `Assistant`
- `Document`
- `Conversation`
- `ChatMessage`
- contratos de repositório
- contratos de embeddings, vector store e LLM

### Application

Contém casos de uso e serviços de aplicação:

- criar e listar assistentes
- registrar documentos
- ingerir documentos
- enviar mensagem para um assistente
- recuperar histórico

### Infrastructure

Implementa detalhes externos:

- persistência PostgreSQL
- client Qdrant
- geração local de embeddings
- adapters de LLM
- grafo conversacional com LangGraph

### API

Expõe a aplicação via FastAPI:

- rotas HTTP
- schemas de request/response
- injeção de dependências
- tratamento de erros de borda

## Regra de Dependência

Dependências apontam para dentro:

`api -> application -> domain`

`infrastructure -> application/domain`

O domínio não deve importar FastAPI, SQLAlchemy, Qdrant, LangGraph ou SDKs de LLM.
