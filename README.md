# Nexus

> Uma plataforma RAG para centralizar conhecimento organizacional em assistentes conversacionais — projeto de pós-graduação.

---

## A História por Trás do Projeto

Toda organização acumula conhecimento. Manuais, atas, políticas, wikis, arquivos em pastas compartilhadas. O problema não é falta de informação — é encontrar a informação certa, no momento certo, sem depender de quem "sabe de cabeça".

A pergunta que motivou o Nexus foi simples: **e se qualquer pessoa pudesse conversar com os documentos oficiais da empresa e receber respostas confiáveis, ancoradas naquele conteúdo?**

O caminho escolhido foi RAG — Retrieval-Augmented Generation. Em vez de confiar apenas no que o modelo de linguagem "aprendeu", a arquitetura recupera trechos relevantes dos documentos antes de gerar cada resposta. O resultado é rastreável: a resposta vem do que está escrito, não de uma inferência genérica.

O Nexus foi construído como projeto de pós-graduação, em ciclos incrementais, começando pela documentação antes do código. Cada decisão foi registrada como ADR. Cada etapa foi validada com critérios explícitos.

---

## O Que o Nexus Faz

1. **Cria assistentes** — cada um representa uma área, projeto ou domínio de conhecimento.
2. **Indexa documentos** — PDFs e DOCX são extraídos, divididos em chunks e vetorizados localmente.
3. **Responde perguntas** — o chat recupera contexto da base do assistente ativo e gera respostas com LLM.
4. **Mantém histórico** — conversas são persistidas e retomadas sem perder contexto.
5. **Isola conhecimento** — assistentes diferentes nunca misturam suas bases de busca.

---

## Como a IA é Usada

### Embeddings Locais

A vetorização dos documentos acontece dentro do próprio container, sem chamadas a APIs externas. O modelo escolhido foi `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — multilíngue, leve e compatível com documentos em português.

Cada chunk recebe um vetor de 384 dimensões e é gravado no Qdrant, na collection isolada do assistente.

### RAG com Isolamento por Assistente

Ao receber uma pergunta, o sistema consulta **apenas** a collection do assistente ativo. Não há vazamento de contexto entre assistentes. A busca semântica retorna os trechos mais relevantes, que são injetados no prompt junto com o histórico da conversa.

### Fluxo Conversacional com LangGraph

O grafo LangGraph coordena as etapas da conversa de forma explícita e testável:

```
Mensagem → Carregar histórico → Recuperar contexto RAG
         → Avaliar relevância
         → [contexto suficiente] Gerar resposta com LLM
         → [contexto insuficiente] Fallback: "não há evidência suficiente"
         → Persistir pergunta e resposta
```

A avaliação de relevância garante que o assistente não invente respostas quando a base não contém informação suficiente. O fallback é explícito — é uma decisão de produto, não um comportamento acidental.

### Provedor de LLM Configurável

O adapter de LLM é uma interface. A implementação concreta é definida por variável de ambiente, permitindo trocar o provedor sem alterar o domínio ou os casos de uso.

---

## Arquitetura

```mermaid
flowchart LR
    User[Usuário] --> FE[Angular + NgRx]
    FE --> API[FastAPI]
    API --> UC[Use Cases]
    UC --> DB[(PostgreSQL)]
    UC --> RAG[LangGraph RAG]
    RAG --> VDB[(Qdrant)]
    RAG --> LLM[LLM Provider]
    DOC[Ingestão de Documentos] --> EMB[Embeddings Locais]
    EMB --> VDB
```

O backend segue **Clean Architecture** com quatro camadas:

| Camada | Responsabilidade |
|---|---|
| `domain` | Entidades, value objects e interfaces — sem dependência de frameworks |
| `application` | Casos de uso e serviços de aplicação |
| `infrastructure` | PostgreSQL, Qdrant, embeddings, LLM, LangGraph |
| `api` | Rotas FastAPI, schemas, injeção de dependências |

A regra de dependência é unidirecional: `api → application → domain`. O domínio não conhece FastAPI, SQLAlchemy, Qdrant ou qualquer SDK de IA.

---

## Stack de Ferramentas

| Categoria | Ferramenta | Por quê |
|---|---|---|
| Backend | FastAPI | Performance, tipagem nativa e geração automática de docs |
| ORM | SQLAlchemy 2.x | Async-first, compatível com psycopg3 |
| Banco relacional | PostgreSQL | Persistência de assistentes, conversas e histórico |
| Busca vetorial | Qdrant | Collections isoladas por assistente, fácil de rodar local |
| Embeddings | sentence-transformers | Multilíngue, local, sem custo por chamada |
| Grafo de IA | LangGraph | Fluxo conversacional explícito e testável |
| Extração de docs | PyPDF + python-docx | Suporte a PDF e DOCX sem dependências pesadas |
| Frontend | Angular 17+ | Framework robusto com lazy loading e standalone components |
| Estado | NgRx | Store reativa, rastreável e testável |
| Estilo | Tailwind CSS | Utilidade-first, consistência sem CSS custom |
| Ambiente | Docker Compose | Uma única dependência para rodar tudo localmente |

---

## Execução Local

```bash
# 1. Configure as variáveis de ambiente
cp .env.example .env

# 2. Suba o ambiente completo
docker compose up -d --build

# 3. Acesse
# Frontend:        http://localhost:4200  (leva ao login do Keycloak)
# Keycloak:        http://localhost:8080
# Backend (docs):  http://localhost:8000/docs
# Backend (health): http://localhost:8000/health
```

O acesso exige login. O realm de desenvolvimento traz usuários fictícios, todos com a senha
`nexus-dev`: `admin.nexus` (administrador), `curadora.rh` (curadora), `usuario.rh`,
`usuario.financeiro` e `diretora`. Papéis, grupos e o console do Keycloak estão em
[`infra/keycloak/README.md`](infra/keycloak/README.md). Assistentes criados antes da autenticação
só aparecem para o administrador até serem vinculados a um grupo.

Para o guia de validação ponta a ponta (assistente → documento → chat → histórico), consulte [`docs/infraestrutura/docker-local.md`](docs/infraestrutura/docker-local.md).

---

## Estrutura do Monorepo

```
nexus/
├── backend/            # FastAPI + Clean Architecture
│   └── src/
│       ├── api/        # Rotas e schemas
│       ├── application/# Casos de uso
│       ├── domain/     # Entidades e interfaces
│       └── infrastructure/ # PostgreSQL, Qdrant, LLM, LangGraph
├── frontend/           # Angular + NgRx + Tailwind
│   └── src/app/
│       ├── features/   # assistants, chat, documents
│       └── store/      # NgRx store, actions, effects
├── docs/
│   ├── arquitetura/    # ADRs, C4, fluxos
│   ├── especificacao/  # Requisitos, histórias, casos de uso, specs SDD
│   ├── gestao-riscos/  # Identificação, análise e resposta a riscos
│   ├── infraestrutura/ # Docker, variáveis, troubleshooting
│   ├── negocio/        # Visão, escopo, público, glossário
│   └── qa/             # Roteiros de validação manual
├── compose.yaml
└── .env.example
```

---

## Lições Aprendidas

**Documentar antes de codar funciona.** Começar pelos ADRs e pela visão de produto forçou decisões explícitas antes que o código tornasse tudo mais difícil de mudar. Mudar um documento é barato. Mudar uma abstração depois de implementada, não.

**RAG não é mágico — é um contrato.** A qualidade da resposta depende da qualidade da recuperação. Chunks mal dimensionados ou coleções mal isoladas geram respostas irrelevantes. O fallback explícito ("não há evidência suficiente") foi uma das decisões mais importantes do produto: preferir honestidade a alucinação.

**Embeddings locais valem o esforço.** Mover a vetorização para dentro do container eliminou latência variável, custo por chamada e dependência de disponibilidade externa. Para um MVP com volume imprevisível de documentos, foi a escolha certa.

**Clean Architecture paga o custo de setup.** Testar casos de uso sem Docker, sem banco, sem LLM real acelera o ciclo de desenvolvimento. O esforço inicial de definir interfaces e separar camadas se justificou nas primeiras semanas de implementação.

**LangGraph torna o fluxo auditável.** Em vez de código sequencial espalhado, o grafo torna as etapas visíveis, nomeadas e testáveis individualmente. Isso foi especialmente útil para o fallback — ficou claro exatamente onde e quando ele é ativado.

**Isolamento por collection é simples e funciona.** A estratégia de uma collection Qdrant por assistente pode parecer excessiva, mas elimina qualquer risco de mistura de contexto no MVP. É o tipo de decisão que vale errar pelo lado da segurança.

---

## Evolução: RAG Enterprise

O MVP comprovou o ciclo completo. O próximo passo é levar o RAG ao nível corporativo: respostas mais precisas e verificáveis, acesso controlado e operação mensurável. As seis fases estão especificadas; **a Fase 1 já está implementada** e em validação no ambiente Docker, e as demais ainda não foram iniciadas.

### Onde o MVP está hoje

Uma revisão do código mostrou diferenças entre o que este README descreve e o que está implementado:

| Aspecto | Implementação atual | Evolução planejada |
|---|---|---|
| Embeddings | Hash determinístico de palavras em 384 posições (`LocalHashEmbeddingGateway`); o modelo citado acima ainda não é carregado | Modelo semântico local da ADR 0004 |
| Chunking | Corte fixo de 700 caracteres | Por estrutura do documento, medido em tokens |
| Busca | Densa, quatro vizinhos, sem nota mínima | Híbrida (densa + BM25), reranking local e nota mínima |
| Fallback | Só quando a busca não devolve nenhum trecho | Por nota mínima de relevância |
| Fontes | Não exibidas | Citação de documento, seção e página |
| Acesso | Sem autenticação | Keycloak, papéis e grupos por assistente e por documento |
| Ingestão | Síncrona, sem exclusão de documento | Em segundo plano, com ciclo de vida completo |
| Qualidade | Medida sob demanda por um comando, com conjunto de referência piloto (Fase 1) | Avaliação contínua na integração |
| Logs | Estruturados em JSON, com identificador de requisição (Fase 1) | Rastreamento, métricas e custo por conversa |

### Decisões fixadas

- **Embeddings continuam locais**, como na ADR 0004. Vetorização, busca esparsa, reranking e OCR rodam no próprio ambiente.
- **Keycloak é sempre o provedor de identidade.**

### Seis fases, especificadas com SDD

Cada fase tem uma especificação que precisa ser aprovada antes de qualquer código, com critérios de aceite em Gherkin e testes escritos antes da implementação.

| Fase | Entrega | Especificação | Situação |
|---|---|---|---|
| 1 | Avaliação e linha de base | [SPEC-001](docs/especificacao/specs/SPEC-001-avaliacao-e-linha-de-base.md) | Implementada, em validação |
| 2 | Recuperação semântica | [SPEC-002](docs/especificacao/specs/SPEC-002-recuperacao-semantica.md) | Código entregue; validação no Docker pendente |
| 3 | Busca híbrida, reranking e citações | [SPEC-003](docs/especificacao/specs/SPEC-003-busca-hibrida-reranking-citacoes.md) | Código entregue; validação no Docker pendente |
| 4 | Autenticação e controle de acesso | [SPEC-004](docs/especificacao/specs/SPEC-004-autenticacao-e-controle-de-acesso.md) | Código entregue; validação no Docker pendente |
| 5 | Ingestão e ciclo de vida de documentos | [SPEC-005](docs/especificacao/specs/SPEC-005-ingestao-e-ciclo-de-vida.md) | Especificada |
| 6 | Operação e governança | [SPEC-006](docs/especificacao/specs/SPEC-006-operacao-e-governanca.md) | Especificada |

### Medindo a qualidade (Fase 1)

Com o ambiente no ar:

```bash
scripts/eval.sh nexus-docs        # Linux, macOS ou Git Bash
scripts\eval.ps1 nexus-docs       # Windows PowerShell
```

O comando indexa a documentação do próprio Nexus em um assistente piloto, executa 27 perguntas de referência e grava um relatório com recall@5, MRR, fidelidade e fallback correto, comparando com a execução anterior. Detalhes em [`backend/tests/evaluation/README.md`](backend/tests/evaluation/README.md).

### Arquitetura alvo

```mermaid
flowchart LR
    User[Usuário] --> FE[Angular + NgRx]
    FE -->|login| KC[Keycloak]
    FE -->|token| API[FastAPI]
    API --> UC[Use Cases + Política de Acesso]
    UC --> DB[(PostgreSQL)]
    UC --> RAG[LangGraph RAG]
    RAG --> HYB[Busca híbrida + Reranker local]
    HYB --> VDB[(Qdrant)]
    RAG --> LLM[LLM Provider]
    API -->|fila| WK[Worker de Ingestão]
    WK --> EMB[Embeddings locais + BM25]
    EMB --> VDB
```

O backend continua em Clean Architecture: tudo o que é novo entra atrás de portas do domínio, e o worker de ingestão é o mesmo código do backend, não um microsserviço.

A documentação desta evolução foi gerada com apoio de IA generativa. O autor aprovou a SPEC-001 e validou o conjunto de referência piloto; o restante está **pendente de revisão do autor**.

---

## Documentação

| Documento | Descrição |
|---|---|
| [Visão do produto](docs/negocio/visao-produto.md) | Contexto, proposta de valor e resultado esperado |
| [Escopo do MVP](docs/negocio/escopo-mvp.md) | O que está dentro e fora do escopo, critérios de aceite |
| [Problema e Solução](docs/negocio/problema-e-solucao.md) | O problema organizacional que o Nexus resolve |
| [Visão geral da arquitetura](docs/arquitetura/visao-geral.md) | Diagrama, componentes e decisões macro |
| [Clean Architecture no backend](docs/arquitetura/clean-architecture-backend.md) | Camadas, regras de dependência e exemplos |
| [Fluxo RAG e isolamento](docs/arquitetura/rag-e-isolamento-de-conhecimento.md) | Estratégia de ingestão e separação por assistente |
| [LangGraph conversacional](docs/arquitetura/langgraph-fluxo-conversacional.md) | Etapas do grafo, memória e regras de produto |
| [Plano incremental](docs/plano-incremental.md) | As 8 etapas de construção do MVP e as 6 etapas da evolução RAG Enterprise |
| [Docker local](docs/infraestrutura/docker-local.md) | Guia de execução e validação local |
| [Gestão de riscos e comunicação](docs/gestao-riscos/README.md) | Atividade de identificação, análise e resposta a riscos com apoio de genAI |
| [Especificação de requisitos](docs/especificacao/README.md) | Requisitos, regras de negócio, histórias, critérios de aceitação e casos de uso |
| [Especificações SDD da evolução](docs/especificacao/specs/README.md) | Uma especificação por fase da evolução RAG Enterprise |
| [Estratégia de testes](docs/especificacao/estrategia-de-testes.md) | Níveis de teste e casos de teste da evolução |
| [Escopo da evolução RAG Enterprise](docs/negocio/escopo-rag-enterprise.md) | Objetivo de negócio, escopo, benefícios e critérios de aceite |
| [ADRs](docs/arquitetura/adrs) | Decisões arquiteturais; 0006 a 0011 tratam da evolução |
| [Validação manual da evolução](docs/qa/validacao-manual-rag-enterprise.md) | Roteiro ponta a ponta por fase |
| [Avaliação de qualidade](backend/tests/evaluation/README.md) | Conjunto de referência, comando de avaliação e métricas |
