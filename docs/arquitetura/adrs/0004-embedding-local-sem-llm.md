# ADR 0004: Embeddings Locais sem Chamada à LLM

## Status

Aceita.

## Contexto

Embeddings serão gerados em volume durante ingestão e reprocessamento de documentos. Usar APIs
externas desde o início aumenta custo, latência e dependência operacional.

## Decisão

Gerar embeddings localmente, via runtime no container backend, sem chamar LLM externa nessa etapa.

### Modelo Inicial Recomendado

- **Modelo**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **Dimensão do vetor**: 384.
- **Justificativa**:
  - melhor cobertura para documentos e perguntas em portugues no contexto do MVP;
  - custo computacional viavel para execucao local via Docker;
  - dimensao 384 reduz uso de memoria no Qdrant sem sacrificar qualidade inicial.

### Diretriz de Configuração

- O dimensionamento da collection no Qdrant deve iniciar em `384`.
- A troca de modelo deve ser parametrizável por variável de ambiente.
- Ao trocar modelo, deve existir rotina explícita de reindexação das collections afetadas.
- O nome do modelo deve ser centralizado em `EMBEDDING_MODEL_NAME`.

## Consequências

- O ambiente Docker deve incluir o runtime necessário para embeddings.
- O tamanho do modelo precisa equilibrar qualidade e custo local.
- A dimensão dos vetores deve ser compatível com as collections do Qdrant.
- O provedor de LLM continua separado e usado apenas na geração de respostas.
- A troca futura para outro modelo continua permitida, desde que acompanhada de migracao/reindexacao.
