# ADR 0006: Embeddings Semânticos Locais e Estratégia de Reindexação

## Status

Aceita em 2026-10-07, com a aprovação da SPEC-002. Implementada; ainda não
executada no ambiente Docker. Complementa a [ADR 0004](0004-embedding-local-sem-llm.md), sem alterá-la.

## Contexto

A ADR 0004 definiu embeddings locais com o modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. A implementação do MVP, porém,
utiliza `LocalHashEmbeddingGateway`, um hash determinístico de palavras em 384 posições, que não
captura significado. As variáveis `EMBEDDING_MODEL_NAME` e `EMBEDDING_VECTOR_SIZE` existem, mas
apenas a segunda é lida pelo código.

A própria ADR 0004 exige rotina explícita de reindexação ao trocar de modelo, e essa rotina não
existe. Os vetores de hash atuais são incompatíveis com qualquer modelo real.

## Decisão

1. **Manter embeddings locais**, como determina a ADR 0004, e implementá-los de fato com o modelo
   nela indicado, por meio de um adaptador `SentenceTransformerEmbeddingGateway`.
2. Manter `LocalHashEmbeddingGateway` apenas como dublê de testes unitários.
3. Versionar as collections (`assistant-{assistant_id}-v{n}`) e usar o nome
   `assistant-{assistant_id}` como **alias** do Qdrant para a versão vigente.
4. Reindexar por construção de uma nova versão e troca atômica de alias, sem indisponibilidade.
5. Registrar em cada documento e em cada chunk o modelo de embedding e a versão do pipeline.
6. Limitar o tamanho do chunk, em tokens, à capacidade do modelo carregado; o adaptador recusa
   configuração que a exceda.
7. Manter os modelos em um volume de cache (`backend_cache`), já previsto na documentação de
   infraestrutura.

## Consequências

- A busca passa a ser semântica; o ganho é medido pela avaliação da SPEC-001.
- A imagem do backend cresce com `sentence-transformers` e PyTorch (CPU); o primeiro uso baixa o modelo.
- Toda a base existente precisa ser reprocessada, com novo upload enquanto os arquivos originais
  não forem armazenados (ADR 0009).
- O limite de sequência do modelo escolhido é curto, o que impõe chunks pequenos e aumenta a
  quantidade de vetores.
- A troca de modelo continua possível por variável de ambiente, sempre seguida de reindexação (RN-16).
- A ADR 0003 permanece válida: o alias preserva o isolamento por assistente.

## Alternativas Consideradas

- **API externa de embeddings:** descartada por contrariar a ADR 0004; documentos sairiam do ambiente.
- **Modelo local maior:** pode melhorar a qualidade, mas aumenta memória e latência em CPU. Fica
  como opção futura, condicionada ao resultado da avaliação e a nova decisão registrada.
- **Reindexar na mesma collection:** descartada por causar indisponibilidade e estado misto de vetores.
