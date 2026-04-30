# Nexus

O Nexus é uma plataforma de chatbot para centralizar conhecimento organizacional com RAG
(Retrieval-Augmented Generation). Ele permite criar assistentes especializados por área,
departamento ou projeto, mantendo cada base de conhecimento isolada e rastreável.

## Objetivo do MVP

O MVP deve provar o fluxo essencial:

1. Criar um assistente.
2. Enviar documentos oficiais para a base desse assistente.
3. Fazer perguntas em linguagem natural.
4. Receber respostas baseadas nos documentos recuperados.
5. Retomar conversas com histórico persistente.

## Organização Inicial

- `docs/negocio`: visão de produto, problema, público, escopo e glossário.
- `docs/arquitetura`: decisões técnicas, visão macro e arquitetura alvo.
- `docs/infraestrutura`: requisitos e operação local com Docker.
- `backend`: futura API FastAPI organizada por Clean Architecture.
- `frontend`: futura aplicação Angular com Tailwind e NgRx.
- `infra/docker`: imagens e scripts auxiliares para execução local.
- `scripts`: comandos de desenvolvimento, testes e lint.

## Documentação Principal

- [Visão do produto](docs/negocio/visao-produto.md)
- [Escopo do MVP](docs/negocio/escopo-mvp.md)
- [Visão geral da arquitetura](docs/arquitetura/visao-geral.md)
- [Plano incremental](docs/plano-incremental.md)
- [Docker local](docs/infraestrutura/docker-local.md)
