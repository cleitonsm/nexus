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
