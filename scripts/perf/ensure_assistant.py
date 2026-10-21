"""V7: garante o assistente das medicoes de desempenho e grava o id dele.

Roda no container do backend (``NEXUS_TEST_USER``/``NEXUS_TEST_PASSWORD`` do cliente
``nexus-tests`` ou ``NEXUS_TOKEN``, como em ``common.get_token``):

  python /app/scripts/perf/ensure_assistant.py --base-url http://backend:8000 \
    --name "Desempenho V7" --out /app/out/07-desempenho/assistant-id.txt

Reaproveita o assistente de mesmo nome, se houver; senao cria um (administrador).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from common import api_headers, get_token, request
except ImportError:  # pragma: no cover
    from scripts.perf.common import api_headers, get_token, request


def ensure(base_url: str, name: str, token: str) -> str:
    status, _, payload = request("GET", f"{base_url}/assistants", headers=api_headers(token))
    if status != 200:
        raise RuntimeError(f"listing assistants failed with status {status}.")
    for item in json.loads(payload):
        if item.get("name") == name:
            return str(item["id"])
    body = json.dumps({"name": name, "description": "Medicoes de desempenho da V7"}).encode()
    headers = {**api_headers(token), "Content-Type": "application/json"}
    status, _, payload = request("POST", f"{base_url}/assistants", headers=headers, body=body)
    if status != 201:
        raise RuntimeError(f"creating assistant failed with status {status}: {payload[:200]!r}.")
    return str(json.loads(payload)["id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://backend:8000")
    parser.add_argument("--name", default="Desempenho V7")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    assistant_id = ensure(args.base_url.rstrip("/"), args.name, get_token())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(assistant_id + "\n", encoding="utf-8")
    print(assistant_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
