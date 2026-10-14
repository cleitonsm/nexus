"""Apoio do CT-53: cria o documento, espera o estado e confere o resultado.

Roda no container do backend, com ``backend/tests/integration`` montado em
``/app/integration`` e ``scripts`` em ``/app/scripts``. Subcomandos:

* ``start``   cria um assistente, envia um PDF de ~10 MB e espera ``processando``;
              imprime ``ASSISTANT=<id>`` e ``DOCUMENT=<id>``.
* ``wait``    espera o documento chegar a ``indexado`` (``--timeout`` s) e
              roda a conferencia PostgreSQL x Qdrant do assistente.
* ``status``  imprime o estado atual do documento.
* ``cleanup`` exclui o assistente.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/app/integration")
sys.path.insert(0, "/app/scripts/perf")

import corpus  # noqa: E402
from stack_support import Api, token_for  # noqa: E402


def _api() -> Api:
    return Api(token_for("admin.nexus"))


def start(seed: int) -> int:
    api = _api()
    status, data = api.json(
        "POST", "/assistants", payload={"name": f"CT-53 {int(time.time())}-{seed}"}
    )
    if status != 201:
        print(f"falha ao criar assistente: {status} {data}")
        return 2
    with tempfile.TemporaryDirectory() as directory:
        pdf = corpus.make_text_pdf(Path(directory) / "job.pdf", 10 * corpus.MB, seed)
        status, document = api.upload(
            data["id"], f"ct53-{seed}.pdf", pdf.read_bytes(), content_type="application/pdf"
        )
    if status != 202:
        print(f"falha no envio: {status} {document}")
        return 2
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        _, current = api.json("GET", f"/documents/{document['id']}")
        if current["status"] == "processando":
            break
        if current["status"] in ("indexado", "falhou"):
            print(f"o job terminou antes da interrupcao ({current['status']}); use arquivo maior")
            return 3
        time.sleep(0.5)
    else:
        print("o documento nao entrou em processamento")
        return 2
    print(f"ASSISTANT={data['id']}")
    print(f"DOCUMENT={document['id']}")
    return 0


def wait(document_id: str, assistant_id: str, timeout: float) -> int:
    api = _api()
    try:
        done = api.wait_indexed(document_id, timeout=timeout)
    except TimeoutError as exc:
        print(f"FALHA: {exc}")
        return 1
    print(f"estado final: {done['status']}, trechos: {done['chunk_count']}")
    if done["status"] != "indexado":
        print(f"FALHA: motivo = {done.get('failure_reason')}")
        return 1
    # Trechos duplicados aparecem como divergencia de contagem.
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.check_consistency", "--assistant", assistant_id],
        cwd="/app",
    )
    if result.returncode != 0:
        print("FALHA: conferencia PostgreSQL x Qdrant divergente")
        return 1
    print("OK")
    return 0


def status_of(document_id: str) -> int:
    _, current = _api().json("GET", f"/documents/{document_id}")
    print(current["status"])
    return 0


def cleanup(assistant_id: str) -> int:
    _api().request("DELETE", f"/assistants/{assistant_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start")
    s.add_argument("--seed", type=int, default=53)
    w = sub.add_parser("wait")
    w.add_argument("--document", required=True)
    w.add_argument("--assistant", required=True)
    w.add_argument("--timeout", type=float, default=300)
    t = sub.add_parser("status")
    t.add_argument("--document", required=True)
    c = sub.add_parser("cleanup")
    c.add_argument("--assistant", required=True)
    args = parser.parse_args()
    if args.command == "start":
        return start(args.seed)
    if args.command == "wait":
        return wait(args.document, args.assistant, args.timeout)
    if args.command == "status":
        return status_of(args.document)
    return cleanup(args.assistant)


if __name__ == "__main__":
    raise SystemExit(main())
