"""RNF-02: do 202 ate o documento ficar ``indexado`` (consulta ``GET /documents/{id}``).

Cada arquivo e enviado sozinho, com a fila vazia. A amostra tem status ``200``
quando termina em ``indexado``; ``falhou`` ou excesso de tempo viram erro.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    from common import (
        Sample, TokenSource, api_headers, as_token_source, new_request_id, now_iso, request, write_samples,
    )
    from upload_latency import multipart
except ImportError:  # pragma: no cover
    from scripts.perf.common import (
        Sample, TokenSource, api_headers, as_token_source, new_request_id, now_iso, request, write_samples,
    )
    from scripts.perf.upload_latency import multipart


def measure_one(
    base_url: str,
    assistant_id: str,
    token: str,
    path: Path,
    *,
    poll_s: float = 1.0,
    timeout_s: float = 900.0,
) -> Sample:
    token_source = as_token_source(token)
    request_id = new_request_id()
    start_iso, started = now_iso(), time.perf_counter()
    body, content_type = multipart("file", path.name, path.read_bytes())
    status, _, payload = request(
        "POST",
        f"{base_url}/assistants/{assistant_id}/documents",
        headers={**api_headers(token_source(), request_id), "Content-Type": content_type},
        body=body,
    )
    result = str(status)
    if status == 202:
        document_id = json.loads(payload)["id"]
        result = "timeout"
        while time.perf_counter() - started < timeout_s:
            code, _, body_bytes = request(
                "GET", f"{base_url}/documents/{document_id}", headers=api_headers(token_source())
            )
            state = json.loads(body_bytes).get("status") if code == 200 else None
            if state == "indexado":
                result = "200"
                break
            if state == "falhou":
                result = "falhou"
                break
            time.sleep(poll_s)
    return Sample(start_iso, now_iso(), time.perf_counter() - started, result, request_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--assistant-id", required=True)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--glob", default="index-*")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args(argv)
    files = sorted(args.files.glob(args.glob))
    if not files:
        raise SystemExit("no files to index.")
    token = TokenSource()
    samples = [
        measure_one(args.base_url.rstrip("/"), args.assistant_id, token, path, timeout_s=args.timeout)
        for path in files
    ]
    write_samples(args.out, samples)
    failed = [sample.status for sample in samples if sample.status != "200"]
    if failed:
        print(f"{len(failed)} de {len(samples)} indexacoes falharam: {sorted(set(failed))}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
