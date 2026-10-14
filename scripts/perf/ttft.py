"""RNF-01: tempo ate o primeiro evento de texto (``delta``) na rota de streaming.

Cada amostra cria uma conversa nova e faz uma pergunta; ``--concurrency``
dispara perguntas simultaneas. A amostra e ``200`` se o primeiro evento ``delta``
(ou ``replace``) chegou, e o tempo vai ate esse evento.
"""

from __future__ import annotations

import argparse
import http.client
import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

try:
    from common import Sample, api_headers, get_token, new_request_id, now_iso, request, write_samples
except ImportError:  # pragma: no cover
    from scripts.perf.common import Sample, api_headers, get_token, new_request_id, now_iso, request, write_samples

TEXT_EVENTS = {"delta", "replace"}


def first_text_event_seconds(lines, started: float) -> float | None:
    """Tempo ate o primeiro evento de texto num fluxo SSE (linhas ja decodificadas)."""
    event = None
    for line in lines:
        line = line.rstrip("\r\n")
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event in TEXT_EVENTS:
            return time.perf_counter() - started
        elif line == "":
            event = None
    return None


def ask_timed(base_url: str, token: str, assistant_id: str, question: str) -> Sample:
    """Como ``ask``, mas a duracao registrada e a do primeiro evento de texto."""
    request_id = new_request_id()
    start_iso, started = now_iso(), time.perf_counter()
    headers = {**api_headers(token, request_id), "Content-Type": "application/json"}
    try:
        code, _, payload = request(
            "POST",
            f"{base_url}/conversations",
            headers=headers,
            body=json.dumps({"assistant_id": assistant_id}).encode(),
        )
        if code not in (200, 201):
            return Sample(start_iso, now_iso(), time.perf_counter() - started, str(code), request_id)
        conversation_id = json.loads(payload)["id"]
        parts = urlsplit(base_url)
        connection = http.client.HTTPConnection(parts.netloc, timeout=180)
        try:
            begin = time.perf_counter()
            connection.request(
                "POST",
                f"{parts.path}/conversations/{conversation_id}/chat/stream",
                body=json.dumps({"question": question}).encode(),
                headers=headers,
            )
            response = connection.getresponse()
            if response.status != 200:
                return Sample(start_iso, now_iso(), time.perf_counter() - begin, str(response.status), request_id)
            elapsed = first_text_event_seconds(
                (raw.decode("utf-8", "replace") for raw in response), begin
            )
        finally:
            connection.close()
    except Exception as exc:  # noqa: BLE001
        return Sample(start_iso, now_iso(), time.perf_counter() - started, f"error:{type(exc).__name__}", request_id)
    status = "200" if elapsed is not None else "sem-texto"
    return Sample(start_iso, now_iso(), elapsed if elapsed is not None else time.perf_counter() - begin, status, request_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--assistant-id", required=True)
    parser.add_argument("--questions", required=True, help="arquivo com uma pergunta por linha")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    with open(args.questions, encoding="utf-8") as handle:
        questions = [line.strip() for line in handle if line.strip()]
    if not questions:
        raise SystemExit("no questions.")
    token = get_token()
    base = args.base_url.rstrip("/")
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        samples = list(
            pool.map(
                lambda i: ask_timed(base, token, args.assistant_id, questions[i % len(questions)]),
                range(args.samples),
            )
        )
    write_samples(args.out, samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
