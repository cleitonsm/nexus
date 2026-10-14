"""RNF-18: carga de consultas (RNF-16) durante a reindexacao do assistente.

Roda no container do backend (``NEXUS_TOKEN`` ou ``NEXUS_TEST_USER`` e
``NEXUS_TEST_PASSWORD`` para o token, como em ``common.get_token``):

  docker compose run --rm --no-deps -v ./scripts:/app/scripts:ro -v ./tmp/perf:/app/perf \
    backend python /app/scripts/perf/reindex_under_load.py \
    --assistant-id ID --chunks /app/perf/chunks.jsonl --users 1 --out /app/perf/rnf18.csv

Dispara ``POST /assistants/ID/reindex`` e, enquanto o worker reindexa, repete
consultas hibridas (``retrieval_latency.measure_hybrid``) em ciclos de
``--batch`` perguntas ate o job terminar. O CSV tem uma linha por consulta;
compare o p95 com o do RNF-16 (``report.py``). Criterio (V-D6): zero erros e
p95 ate +20% sobre a linha de base. O assistente deve ter a base do RNF-16
(corpus de ``corpus.py`` enviado pela API).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    from common import api_headers, get_token, request, write_samples
    from retrieval_latency import load_queries, measure_hybrid
except ImportError:  # pragma: no cover
    from scripts.perf.common import api_headers, get_token, request, write_samples
    from scripts.perf.retrieval_latency import load_queries, measure_hybrid

TERMINAL = ("succeeded", "failed")


def start_reindex(base_url: str, assistant_id: str, token: str) -> dict:
    status, _, body = request(
        "POST",
        f"{base_url}/assistants/{assistant_id}/reindex",
        headers=api_headers(token),
    )
    if status != 202:
        raise SystemExit(f"reindex did not start: {status} {body[:200]!r}")
    return json.loads(body)


def job_state(base_url: str, assistant_id: str, token: str) -> str:
    status, _, body = request(
        "GET",
        f"{base_url}/assistants/{assistant_id}/index-status",
        headers=api_headers(token),
    )
    if status != 200:
        return f"http-{status}"
    data = json.loads(body)
    job = data.get("last_reindex") or {}
    return str(job.get("status", "")).lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://backend:8000")
    parser.add_argument("--assistant-id", required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--users", type=int, default=1)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--max-minutes", type=int, default=240)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    token = get_token()
    queries = load_queries(args.chunks, args.batch)
    start_reindex(base_url, args.assistant_id, token)
    print("reindexacao iniciada; medindo consultas", flush=True)

    samples = []
    deadline = time.monotonic() + args.max_minutes * 60
    while time.monotonic() < deadline:
        samples.extend(measure_hybrid(args.assistant_id, queries, args.users))
        state = job_state(base_url, args.assistant_id, token)
        if state in TERMINAL:
            print(f"job terminou com estado '{state}'")
            break
    else:
        print("limite de tempo atingido antes do fim do job")
    write_samples(args.out, samples)
    errors = sum(1 for sample in samples if not sample.status.isdigit())
    print(f"{len(samples)} consultas durante a reindexacao, {errors} erros; CSV em {args.out}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
