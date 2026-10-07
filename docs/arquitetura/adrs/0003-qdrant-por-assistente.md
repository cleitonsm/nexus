# ADR 0003: Collection Qdrant por Assistente

## Status

Aceita para o MVP.

## Contexto

O Nexus deve permitir múltiplos assistentes com bases de conhecimento distintas. Misturar
conteúdos entre assistentes compromete confiança e dificulta validação.

## Decisão

Criar uma collection no Qdrant para cada assistente.

## Consequências

- O isolamento é simples de entender e testar.
- A busca de um assistente consulta apenas sua própria collection.
- Operações de exclusão de assistente podem remover a collection inteira.
- Em escala maior, pode ser necessário reavaliar para collections compartilhadas com filtros.

## Evolução RAG Enterprise

A decisão permanece válida. A [ADR 0006](0006-embeddings-reais-e-reindexacao.md) passa a versionar
as collections e a usar `assistant-{assistant_id}` como alias da versão vigente. A
[ADR 0008](0008-keycloak-e-modelo-de-permissoes.md) acrescenta restrição por documento dentro do
assistente, por filtro de payload, sem substituir o isolamento por collection.
