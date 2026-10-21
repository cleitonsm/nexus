"""RNF-17 / CT-40: tempo do upload de arquivos de 25 MB ate o 202.

Uso: ``python upload_latency.py --base-url http://backend:8000 --assistant-id ID
--files DIR --out upload.csv``. Cada arquivo do diretorio e enviado uma vez
(arquivos diferentes entre si, D9); a amostra e o tempo medido no cliente.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

try:
    from common import Sample, api_headers, get_token, request, timed, write_samples
except ImportError:  # pragma: no cover
    from scripts.perf.common import Sample, api_headers, get_token, request, timed, write_samples


def multipart(field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----nexus{uuid.uuid4().hex}"
    head = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + content + tail, f"multipart/form-data; boundary={boundary}"


def upload(base_url: str, assistant_id: str, token: str, path: Path, request_id: str):
    body, content_type = multipart("file", path.name, path.read_bytes())
    headers = {**api_headers(token, request_id), "Content-Type": content_type}
    status, _, _ = request(
        "POST", f"{base_url}/assistants/{assistant_id}/documents", headers=headers, body=body
    )
    return status, None


def warm_up(base_url: str, assistant_id: str, token: str, count: int) -> None:
    """Secao 7.1 do plano de validacao: requisicoes descartadas antes da medicao.

    Arquivos Markdown pequenos e de conteudo unico (a duplicidade por hash responde 409):
    aquecem conexoes, validacao do token e banco sem pesar na fila de ingestao.
    """
    for _ in range(count):
        content = f"# Aquecimento\n\n{uuid.uuid4().hex}\n".encode()
        body, content_type = multipart("file", f"aquecimento-{uuid.uuid4().hex[:8]}.md", content)
        headers = {**api_headers(token), "Content-Type": content_type}
        request("POST", f"{base_url}/assistants/{assistant_id}/documents", headers=headers, body=body)


def measure(base_url: str, assistant_id: str, token: str, files: list[Path]) -> list[Sample]:
    samples = []
    for path in files:
        sample, _ = timed(lambda rid, p=path: upload(base_url, assistant_id, token, p, rid))
        samples.append(sample)
    return samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--assistant-id", required=True)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--glob", default="upload-*")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=10, help="envios descartados (secao 7.1)")
    args = parser.parse_args(argv)
    files = sorted(args.files.glob(args.glob))
    if not files:
        raise SystemExit("no files to upload.")
    token = get_token()
    warm_up(args.base_url.rstrip("/"), args.assistant_id, token, args.warmup)
    samples = measure(args.base_url.rstrip("/"), args.assistant_id, token, files)
    write_samples(args.out, samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
