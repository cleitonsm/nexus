# Problema e Solução

## Problema

O conhecimento organizacional normalmente fica espalhado em arquivos, canais de conversa,
pastas compartilhadas e memória de especialistas. Isso gera respostas inconsistentes,
retrabalho e dificuldade para integrar novas pessoas aos processos.

## Solução

O Nexus usa RAG para buscar trechos relevantes em documentos oficiais antes de gerar uma
resposta. A resposta deve ser construída a partir do contexto recuperado, reduzindo respostas
genéricas e aumentando a rastreabilidade.

## Princípios

- Documentos oficiais são a fonte primária de conhecimento.
- Cada assistente possui uma base de conhecimento isolada.
- Conversas devem preservar histórico sem contaminar a recuperação entre assistentes.
- A arquitetura deve permitir trocar provedores de LLM sem afetar o domínio.
