# Relatorio de avaliacao

- Assistente: `167472e3-4f62-4df5-9b11-74a53786f3ef`
- Gerado em: 2026-10-24T22:58:42.332420+00:00
- k: 5
- Conjunto validado por curador: sim

## Metricas

| Metrica | Valor | Variacao |
|---|---|---|
| recall_at_k | 1.000 | +0.000 |
| mrr | 0.890 | -0.110 |
| faithfulness | n/d | n/d |
| fallback_accuracy | n/d | n/d |
| citation_coverage | n/d | n/d |

## Parametros

- commit: `ct48`
- dataset: `nexus-docs.jsonl`
- embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- embedding_vector_size: `384`
- pipeline_version: `3`
- chunk_max_tokens: `limite do modelo`
- chunk_overlap_sentences: `1`
- chunk_prefix_max_tokens: `32`
- sparse: `bm25 (idf no Qdrant), fusao RRF`
- bm25: `k1=1.2, b=0.75, average_length=64.0`
- reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- retrieval_candidates: `30`
- rerank_top_n: `5`
- relevance_min_score: `0.1`
- context_token_budget: `2000`
- history_token_budget: `1500`
- llm_model: `nao utilizado`
- judge: `nao utilizado`
- tolerance: `0.02`
- item_retries: `nenhum`

## Regressoes

mrr
