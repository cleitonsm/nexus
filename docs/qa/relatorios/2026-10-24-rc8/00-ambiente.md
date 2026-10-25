# Ambiente da validação

- Data (UTC): 2026-10-24T18:45:55Z
- Commit: desconhecido (?)
- Etiqueta: sem etiqueta
- Arquivos alterados na árvore: 0

## Máquina
- Sistema: MINGW64_NT-10.0-26300 3.6.3-7674c51e.x86_64 x86_64
- CPUs: 12
- Modelo da CPU: Intel(R) Core(TM) i7-8750H CPU @ 2.20GHz
- Memória total: 15.8 GiB

## Docker
- Servidor: 29.4.3
- Compose: 5.1.3
- CPUs do Docker: 12
- Memória do Docker (bytes): 8247234560

### Imagens do projeto

## Modelos e parâmetros (de .env.example, sem ler .env)
    EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    EMBEDDING_VECTOR_SIZE=384
    CHUNK_MAX_TOKENS=
    CHUNK_OVERLAP_SENTENCES=1
    CHUNK_PREFIX_MAX_TOKENS=32
    UPLOAD_MAX_BYTES=26214400
    INGESTION_MAX_ATTEMPTS=3
    INGESTION_JOB_TIMEOUT_SECONDS=600
    RERANKER_MODEL_NAME=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
    RETRIEVAL_CANDIDATES=30
    LLM_MODEL=gemini-3.8-flash
