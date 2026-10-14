"""RNF-03 e RNF-16: latencia da busca densa e da recuperacao hibrida.

Roda no container do backend (usa os adaptadores reais, sem HTTP):

  docker compose run --rm --no-deps -v ./scripts:/app/scripts:ro -v ./tmp/perf:/app/perf \
    backend python /app/scripts/perf/retrieval_latency.py load --chunks /app/perf/chunks.jsonl
  docker compose run ... retrieval_latency.py dense  --out /app/perf/rnf03.csv
  docker compose run ... retrieval_latency.py hybrid --out /app/perf/rnf16-u1.csv --users 1
  docker compose run ... retrieval_latency.py hybrid --out /app/perf/rnf16-u5.csv --users 5

* ``load``   grava os trechos de ``chunks.jsonl`` (ate 100.000, ver ``corpus.py``)
             com os vetores reais (densos e BM25) na collection do assistante
             ``--assistant-id`` (padrao ``perf-load``). Demorado em CPU.
* ``dense``  RNF-03: busca densa top-k direto no adaptador do Qdrant, 200 consultas;
             o vetor da consulta e calculado antes e nao entra no tempo.
* ``hybrid`` RNF-16: busca hibrida + RRF + reranking de 30 candidatos pelo
             ``ContextRetriever`` (a etapa de recuperacao do chat), 200 perguntas,
             com ``--users`` consultas simultaneas.

Cada linha do CSV e uma consulta (formato de ``common.py``); ``report.py``
consolida. Use ``--assistant-id`` de um assistente real para medir a base dele.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from common import Sample, new_request_id, now_iso, write_samples
except ImportError:  # pragma: no cover
    from scripts.perf.common import Sample, new_request_id, now_iso, write_samples

DEFAULT_ASSISTANT = "perf-load"
SEED = 20261014


def _collection(assistant_id: str):
    from src.domain import AssistantId, CollectionName

    return CollectionName.from_assistant_id(AssistantId(assistant_id))


def _vector_store():
    from src.infrastructure.vector_store import QdrantVectorStoreGateway

    return QdrantVectorStoreGateway(
        url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "") or None,
    )


def load_queries(path: Path | None, count: int) -> list[str]:
    """Perguntas deterministicas: as primeiras palavras de trechos sorteados."""
    rng = random.Random(SEED)
    if path is None:
        raise SystemExit("--chunks (ou --queries-file) e necessario para sortear perguntas.")
    texts = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if path.suffix == ".jsonl":
                texts.append(json.loads(line)["text"])
            else:
                texts.append(line)
    if not texts:
        raise SystemExit("no queries available.")
    return [" ".join(rng.choice(texts).split()[:8]) for _ in range(count)]


def command_load(args: argparse.Namespace) -> int:
    from src.domain import AssistantId, DocumentId, SparseVector, VectorChunk  # noqa: F401
    from src.infrastructure.composition import (
        build_embedding_gateway,
        build_sparse_embedding_gateway,
    )

    embedding = build_embedding_gateway()
    sparse = build_sparse_embedding_gateway()
    store = _vector_store()
    assistant = AssistantId(args.assistant_id)
    collection = _collection(args.assistant_id)
    if store.collection_exists(collection):
        raise SystemExit(f"{collection.value} ja existe; exclua-a antes de recarregar.")
    store.ensure_collection(collection, embedding.dimension)
    batch: list[dict] = []
    loaded = 0

    def flush() -> None:
        nonlocal loaded, batch
        if not batch:
            return
        texts = [item["text"] for item in batch]
        dense = embedding.embed_documents(texts)
        sparse_vectors = sparse.embed_documents(texts)
        store.upsert_chunks(
            collection,
            [
                VectorChunk(
                    id=item["id"],
                    document_id=DocumentId(item["document"]),
                    assistant_id=assistant,
                    chunk_index=index,
                    source_name=f"{item['document']}.md",
                    content_hash=item["id"],
                    text=item["text"],
                    vector=vector,
                    sparse_vector=sv,
                    embedding_model=embedding.model_name,
                )
                for index, (item, vector, sv) in enumerate(
                    zip(batch, dense, sparse_vectors)
                )
            ],
        )
        loaded += len(batch)
        batch = []
        print(f"{loaded} trechos gravados", flush=True)

    with args.chunks.open(encoding="utf-8") as handle:
        for line in handle:
            batch.append(json.loads(line))
            if len(batch) >= args.batch:
                flush()
            if args.limit and loaded + len(batch) >= args.limit:
                break
    flush()
    print(f"collection {collection.value}: {store.count_points(collection)} pontos")
    return 0


def command_dense(args: argparse.Namespace) -> int:
    from src.domain import SparseVector
    from src.infrastructure.composition import build_embedding_gateway

    embedding = build_embedding_gateway()
    store = _vector_store()
    collection = _collection(args.assistant_id)
    queries = load_queries(args.chunks or args.queries_file, args.queries)
    vectors = [embedding.embed_query(query) for query in queries]
    store.hybrid_search(collection, vectors[0], SparseVector(), 10, user_groups=None)  # aquece
    samples = []
    for vector in vectors:
        samples.append(
            _timed(
                lambda v=vector: store.hybrid_search(
                    collection, v, SparseVector(), args.top_k, user_groups=None
                )
            )
        )
    return _finish(args.out, samples)


def build_retriever():
    from src.application.services import ContextRetriever
    from src.infrastructure.composition import (
        build_embedding_gateway,
        build_reranker_gateway,
        build_sparse_embedding_gateway,
        retrieval_settings,
    )

    return ContextRetriever(
        embedding_gateway=build_embedding_gateway(),
        sparse_embedding_gateway=build_sparse_embedding_gateway(),
        vector_store_gateway=_vector_store(),
        reranker_gateway=build_reranker_gateway(),
        settings=retrieval_settings(),
    )


def measure_hybrid(assistant_id: str, queries: list[str], users: int) -> list[Sample]:
    from src.domain import AssistantId

    retriever = build_retriever()
    assistant = AssistantId(assistant_id)

    def one(query: str) -> Sample:
        def call():
            found = retriever.search(assistant, query, user_groups=None)
            return retriever.rerank(query, found)

        return _timed(call)

    one(queries[0])  # aquece modelos e conexoes
    with ThreadPoolExecutor(max_workers=max(users, 1)) as pool:
        return list(pool.map(one, queries))


def command_hybrid(args: argparse.Namespace) -> int:
    queries = load_queries(args.chunks or args.queries_file, args.queries)
    return _finish(args.out, measure_hybrid(args.assistant_id, queries, args.users))


def _timed(call) -> Sample:
    request_id = new_request_id()
    started_iso, started = now_iso(), time.perf_counter()
    status = "200"
    try:
        call()
    except Exception as exc:  # noqa: BLE001 - a falha vira linha do CSV
        status = f"error:{type(exc).__name__}"
    elapsed = time.perf_counter() - started
    return Sample(started_iso, now_iso(), elapsed, status, request_id)


def _finish(out: Path, samples: list[Sample]) -> int:
    write_samples(out, samples)
    durations = sorted(sample.duration_s for sample in samples)
    errors = sum(1 for sample in samples if not sample.status.isdigit())
    p95 = durations[max(0, int(len(durations) * 0.95) - 1)]
    print(
        f"{len(samples)} consultas, mediana {statistics.median(durations):.3f}s, "
        f"p95 {p95:.3f}s, maximo {durations[-1]:.3f}s, erros {errors}; CSV em {out}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("load", "dense", "hybrid"):
        item = sub.add_parser(name)
        item.add_argument("--assistant-id", default=DEFAULT_ASSISTANT)
        item.add_argument("--chunks", type=Path, default=None)
    sub.choices["load"].add_argument("--batch", type=int, default=256)
    sub.choices["load"].add_argument("--limit", type=int, default=0)
    for name in ("dense", "hybrid"):
        item = sub.choices[name]
        item.add_argument("--queries-file", type=Path, default=None)
        item.add_argument("--queries", type=int, default=200)
        item.add_argument("--out", type=Path, required=True)
    sub.choices["dense"].add_argument("--top-k", type=int, default=10)
    sub.choices["hybrid"].add_argument("--users", type=int, default=1)
    args = parser.parse_args(argv)
    return {"load": command_load, "dense": command_dense, "hybrid": command_hybrid}[
        args.command
    ](args)


if __name__ == "__main__":
    raise SystemExit(main())
