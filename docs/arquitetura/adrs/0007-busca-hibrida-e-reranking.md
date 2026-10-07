# ADR 0007: Busca Híbrida e Reranking Locais

## Status

Proposta.

## Contexto

A busca do MVP é apenas densa e devolve sempre os vizinhos mais próximos, sem nota mínima. Busca
densa falha em siglas, códigos e nomes próprios; a ausência de nota mínima faz com que o fallback
quase nunca seja acionado quando a collection tem conteúdo, contrariando a regra de produto de
preferir honestidade a alucinação.

## Decisão

1. Adotar busca híbrida: vetor denso e vetor esparso (BM25) na mesma collection, consultados pela
   Query API do Qdrant com fusão por Reciprocal Rank Fusion.
2. Gerar os vetores esparsos localmente, atrás da porta `SparseEmbeddingGateway`.
3. Reordenar os candidatos com um cross-encoder executado localmente, atrás da porta `RerankerGateway`.
4. Aplicar nota mínima de relevância sobre o resultado do reranking; sem candidatos qualificados,
   o grafo segue para o fallback sem chamar o LLM.
5. Manter todos os parâmetros configuráveis e calibrá-los com o conjunto de referência.

## Consequências

- Mantém-se o princípio da ADR 0004: nenhum conteúdo de documento sai do ambiente na recuperação.
- A versão 1.11.3 do Qdrant, já utilizada, atende à decisão; não há novo serviço.
- As collections precisam ser recriadas com vetores nomeados, usando a reindexação da ADR 0006.
- O reranking em CPU acrescenta latência por pergunta; o número de candidatos é o principal
  controle.
- O fallback volta a cumprir seu papel para perguntas fora do escopo.

## Alternativas Consideradas

- **Somente busca densa com nota mínima:** mais simples, mas não resolve termos exatos.
- **Motor de busca textual separado:** descartado por acrescentar um serviço e duplicar o índice.
- **Reranking por LLM ou por API externa:** descartado por custo, latência e envio de trechos para
  fora do ambiente.
