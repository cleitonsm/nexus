"""RNF-01: tempo ate o primeiro evento de texto (``delta``) na rota de streaming.

Cada amostra cria uma conversa nova e faz uma pergunta; ``--concurrency``
dispara perguntas simultaneas. A amostra e ``200`` se o primeiro evento ``delta``
(ou ``replace``) chegou, e o tempo vai ate esse evento.

Na V7 (decisao do autor, 2026-10-22) roda automaticamente sobre o assistente que a V6
indexa (``--assistant-name``), com as perguntas do escopo do conjunto validado
(``--dataset``, JSONL da avaliacao):

  python ttft.py --base-url http://backend:8000 --assistant-name "Nexus Docs Ampliado (avaliacao)" \
    --dataset /app/datasets/nexus-docs-ampliado.jsonl --out ttft.csv
"""

from __future__ import annotations

import argparse
import http.client
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

try:
    from common import (
        Sample, TokenSource, api_headers, as_token_source, new_request_id, now_iso, request,
        write_samples,
    )
except ImportError:  # pragma: no cover
    from scripts.perf.common import (
        Sample, TokenSource, api_headers, as_token_source, new_request_id, now_iso, request,
        write_samples,
    )

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


class Pacer:
    """Espaca o inicio das perguntas para caber no limite de uso por usuario (RN-32).

    O teste usa um so usuario; acima de ``RATE_LIMIT_PER_MINUTE`` (20) a API responde
    429 de proposito (ensaio de 2026-10-24: 58 de 100). Com 18 por minuto as perguntas
    comecam a cada 3,3 s e ainda se sobrepoem quando a resposta demora.
    """

    def __init__(self, per_minute: float, clock=time.monotonic, sleep=time.sleep) -> None:
        self._interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._next = None
        self._lock = threading.Lock()
        self._clock, self._sleep = clock, sleep

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            start = now if self._next is None else max(now, self._next)
            self._next = start + self._interval
        if start > now:
            self._sleep(start - now)


def dataset_questions(path: str) -> list[str]:
    """Perguntas do escopo (``out_of_scope`` falso) de um conjunto de avaliacao JSONL."""
    questions = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if not item.get("out_of_scope"):
                    questions.append(item["question"])
    return questions


def find_assistant(base_url: str, token: str, name: str) -> str:
    status, _, payload = request("GET", f"{base_url}/assistants", headers=api_headers(token))
    if status != 200:
        raise SystemExit(f"listing assistants failed with status {status}.")
    for item in json.loads(payload):
        if item.get("name") == name:
            return str(item["id"])
    raise SystemExit(f"assistente {name!r} nao encontrado; rode a V6 antes (ela o cria e indexa).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--assistant-id")
    target.add_argument("--assistant-name", help="assistente da V6, procurado pelo nome")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--questions", help="arquivo com uma pergunta por linha")
    source.add_argument("--dataset", help="conjunto JSONL da avaliacao (so perguntas do escopo)")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument(
        "--per-minute", type=float, default=18.0,
        help="perguntas iniciadas por minuto (limite de uso RN-32 = 20); 0 desliga",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.dataset:
        questions = dataset_questions(args.dataset)
    else:
        with open(args.questions, encoding="utf-8") as handle:
            questions = [line.strip() for line in handle if line.strip()]
    if not questions:
        raise SystemExit("no questions.")
    token = as_token_source(TokenSource())  # renova o token nas rodadas longas
    base = args.base_url.rstrip("/")
    assistant_id = args.assistant_id or find_assistant(base, token(), args.assistant_name)
    pacer = Pacer(args.per_minute)

    def one(index: int) -> Sample:
        pacer.wait()  # fora do tempo medido
        return ask_timed(base, token(), assistant_id, questions[index % len(questions)])

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        samples = list(pool.map(one, range(args.samples)))
    write_samples(args.out, samples)
    failed = [sample.status for sample in samples if sample.status != "200"]
    if failed:
        print(f"{len(failed)} de {len(samples)} perguntas sem texto ou com erro: {sorted(set(failed))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
