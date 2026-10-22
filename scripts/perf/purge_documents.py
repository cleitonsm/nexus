"""V7: apaga pela API todos os documentos de um assistente.

A RNF-17 mede so a resposta do upload, com o worker pausado (decisao do autor,
2026-10-22). Os arquivos de 25 MB enviados nessa medicao nao precisam ser indexados:
apagados antes de o worker voltar, saem da fila junto com o documento e nao disputam
a maquina com a RNF-02 nem com a avaliacao do CT-48 (ensaio de 2026-10-22).

Uso: ``python purge_documents.py --base-url http://backend:8000 --assistant-id ID``
"""

from __future__ import annotations

import argparse
import json

try:
    from common import api_headers, get_token, request
except ImportError:  # pragma: no cover
    from scripts.perf.common import api_headers, get_token, request


def purge(base_url: str, assistant_id: str, token: str) -> int:
    status, _, payload = request(
        "GET", f"{base_url}/assistants/{assistant_id}/documents", headers=api_headers(token)
    )
    if status != 200:
        raise SystemExit(f"listing documents failed with status {status}.")
    removed = 0
    for item in json.loads(payload):
        status, _, body = request(
            "DELETE", f"{base_url}/documents/{item['id']}", headers=api_headers(token)
        )
        if status not in (204, 404):
            raise SystemExit(f"deleting document {item['id']} failed: {status} {body[:200]!r}")
        removed += status == 204
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://backend:8000")
    parser.add_argument("--assistant-id", required=True)
    args = parser.parse_args(argv)
    removed = purge(args.base_url.rstrip("/"), args.assistant_id, get_token())
    print(f"{removed} documentos apagados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
