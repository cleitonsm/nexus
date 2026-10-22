"""V7: espera o assistente ficar sem documentos na fila (pendente ou processando).

A RNF-17 e medida com o worker pausado (decisao do autor, 2026-10-22): os arquivos de 25 MB
ficam na fila e so sao indexados quando o worker volta. Antes da RNF-02, que mede do upload
ate o ``indexado``, a fila precisa estar vazia; senao a medicao inclui a espera pelos
documentos anteriores (ensaio de 2026-10-21: timeout de 900 s).

Uso: ``python wait_idle.py --base-url http://backend:8000 --assistant-id ID --wait-minutes 90``
"""

from __future__ import annotations

import argparse
import json
import time

try:
    from common import api_headers, get_token, request
except ImportError:  # pragma: no cover
    from scripts.perf.common import api_headers, get_token, request

BUSY = {"pendente", "processando"}


def busy_documents(base_url: str, assistant_id: str, token: str) -> int:
    status, _, payload = request(
        "GET", f"{base_url}/assistants/{assistant_id}/documents", headers=api_headers(token)
    )
    if status != 200:
        raise SystemExit(f"listing documents failed with status {status}.")
    return sum(1 for item in json.loads(payload) if item.get("status") in BUSY)


def wait_idle(
    base_url: str,
    assistant_id: str,
    *,
    wait_minutes: float,
    poll_seconds: float = 15.0,
    token_source=None,
    sleep=time.sleep,
    clock=time.monotonic,
) -> None:
    token_source = token_source or get_token
    deadline = clock() + wait_minutes * 60
    while True:
        busy = busy_documents(base_url, assistant_id, token_source())
        if busy == 0:
            return
        if clock() >= deadline:
            raise SystemExit(f"{busy} documentos ainda na fila depois de {wait_minutes:g} min.")
        print(f"{busy} documentos na fila; nova verificacao em breve", flush=True)
        sleep(poll_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://backend:8000")
    parser.add_argument("--assistant-id", required=True)
    parser.add_argument("--wait-minutes", type=float, default=90.0)
    args = parser.parse_args(argv)
    wait_idle(args.base_url.rstrip("/"), args.assistant_id, wait_minutes=args.wait_minutes)
    print("fila vazia")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
