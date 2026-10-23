# RAG e Isolamento de Conhecimento

## Estratégia Inicial

Cada assistente terá uma collection própria no Qdrant. Essa decisão torna o isolamento simples,
visível e fácil de testar no MVP.

Exemplo de naming:

```text
assistant-{assistant_id}
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

## Evolução RAG Enterprise

Conteúdo **planejado**; a estratégia inicial acima continua descrevendo o MVP.

### Estado Atual da Implementação

O fluxo de ingestão descrito acima está implementado com duas simplificações: o embedding é um
hash determinístico de palavras, não um modelo semântico, e o chunking corta o texto a cada 700
caracteres. A busca devolve os quatro vizinhos mais próximos, sem nota mínima.

### Collections Versionadas

```text
assistant-{assistant_id}         # alias para a versao vigente
assistant-{assistant_id}-v{n}    # collection fisica
```

A reindexação cria a versão seguinte, confere as contagens e troca o alias de forma atômica.

### Vetores por Chunk

| Vetor | Tipo | Origem |
|-------|------|--------|
| `dense` | 384 dimensões, cosseno | Modelo da ADR 0004, executado localmente |
| `sparse` | BM25 com IDF | Gerado localmente |

### Fluxo de Ingestão Alvo

1. Receber o documento, validar formato e tamanho e verificar duplicidade pelo `content_hash`.
2. Armazenar o arquivo original e registrar o documento como pendente.
3. Enfileirar o processamento e responder ao usuário.
4. No worker: extrair texto estruturado, com OCR para páginas digitalizadas.
5. Fragmentar por estrutura, em tokens, dentro do limite do modelo.
6. Gerar vetores denso e esparso localmente.
7. Remover pontos anteriores do documento e gravar os novos na collection do assistente.
8. Marcar o documento como indexado.

### Metadados por Chunk (acréscimos)

- `section_path`
- `page`
- `embedding_model`
- `pipeline_version`
- `allowed_groups`
- `active`

### Dois Níveis de Isolamento

1. **Entre assistentes**: collection própria por assistente, como no MVP (ADR 0003).
2. **Dentro do assistente**: filtro obrigatório por `allowed_groups`, aplicado na própria consulta
   ao Qdrant, com índice de payload (ADR 0008).

O acesso ao assistente é verificado antes da busca. O filtro de documento só restringe: nunca
concede acesso a quem não pode usar o assistente.

### Critério de Isolamento Ampliado

Além do critério do MVP, uma busca feita por um usuário não deve recuperar chunks de documentos
restritos a grupos aos quais ele não pertence, mesmo que sejam os mais relevantes para a pergunta.

### Recuperação Alvo

Busca híbrida com fusão RRF, reranking local e nota mínima de relevância, conforme a
[ADR 0007](adrs/0007-busca-hibrida-e-reranking.md).

### Medição da Recuperação

Desde a Fase 1, a recuperação é medida pelo comando de avaliação contra um conjunto de referência
(ver `backend/tests/evaluation/README.md`). As metas de recall, fidelidade e fallback estão nos
requisitos RNF-19 a RNF-21, e qualquer mudança nesta estratégia deve ser acompanhada de nova
avaliação (RN-14).
