# RAG e Isolamento de Conhecimento

## Estratégia Inicial

Cada assistente terá uma collection própria no Qdrant. Essa decisão torna o isolamento simples,
visível e fácil de testar no MVP.

Exemplo de naming:

```text
assistant_{assistant_id}
```

## Fluxo de Ingestão

1. Receber documento associado a um assistente.
2. Extrair texto.
3. Dividir o texto em chunks.
4. Gerar embeddings localmente.
5. Gravar vetores e metadados na collection do assistente.

## Metadados Mínimos por Chunk

- `assistant_id`
- `document_id`
- `chunk_index`
- `source_name`
- `content_hash`

## Critério de Isolamento

Uma busca feita para o assistente A deve consultar apenas a collection do assistente A. O backend
não deve recuperar resultados de collections de outros assistentes para responder à pergunta.

## Evolução Futura

Se o número de assistentes crescer muito, a arquitetura pode evoluir para collections
compartilhadas com filtros fortes por `assistant_id`. Essa alternativa não é necessária para o
MVP e aumenta o risco de mistura de contexto.
