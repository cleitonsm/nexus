"""Utilitarios comuns das medicoes (so biblioteca padrao).

Cada cenario grava um CSV com uma linha por amostra:
``start,end,duration_s,status,request_id``. ``report.py`` consolida os CSVs.
"""

from __future__ import annotations

import csv
import http.client
import json
import math
import os
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit

CSV_FIELDS = ("start", "end", "duration_s", "status", "request_id")


@dataclass(frozen=True)
class Sample:
    start: str
    end: str
    duration_s: float
    status: str
    request_id: str


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_request_id() -> str:
    return uuid.uuid4().hex


def write_samples(path: str | Path, samples: Iterable[Sample]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_FIELDS)
        for sample in samples:
            writer.writerow(
                [
                    sample.start,
                    sample.end,
                    f"{sample.duration_s:.6f}",
                    sample.status,
                    sample.request_id,
                ]
            )
    return target


def read_samples(path: str | Path) -> list[Sample]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [
            Sample(
                start=row["start"],
                end=row["end"],
                duration_s=float(row["duration_s"]),
                status=row["status"],
                request_id=row["request_id"],
            )
            for row in csv.DictReader(handle)
        ]


def percentile(values: list[float], fraction: float) -> float:
    """Percentil por posto mais proximo (conservador: nunca subestima)."""
    if not values:
        raise ValueError("no values.")
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1].")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def is_success(status: str) -> bool:
    return status.isdigit() and 200 <= int(status) < 300


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 120.0,
) -> tuple[int, dict[str, str], bytes]:
    parts = urlsplit(url)
    connection_class = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_class(parts.netloc, timeout=timeout)
    try:
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        connection.request(method, target, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        return response.status, dict(response.getheaders()), payload
    finally:
        connection.close()


def get_token(env: dict[str, str] | None = None) -> str:
    """``NEXUS_TOKEN`` ou login pelo cliente ``nexus-tests`` (V-D2, so em dev)."""
    env = env if env is not None else dict(os.environ)
    if env.get("NEXUS_TOKEN"):
        return env["NEXUS_TOKEN"]
    base = env.get("KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
    realm = env.get("KEYCLOAK_REALM", "nexus")
    form = urlencode(
        {
            "grant_type": "password",
            "client_id": env.get("KEYCLOAK_TESTS_CLIENT_ID", "nexus-tests"),
            "username": env["NEXUS_TEST_USER"],
            "password": env["NEXUS_TEST_PASSWORD"],
        }
    )
    status, _, payload = request(
        "POST",
        f"{base}/realms/{realm}/protocol/openid-connect/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=form.encode(),
    )
    if status != 200:
        raise RuntimeError(f"token request failed with status {status}.")
    return json.loads(payload)["access_token"]


def timed(call) -> tuple[Sample, object]:
    """Executa ``call(request_id)`` e devolve a amostra e o resultado."""
    request_id = new_request_id()
    start_iso, started = now_iso(), time.perf_counter()
    status, result = "error", None
    try:
        status, result = call(request_id)
    except Exception as exc:  # noqa: BLE001 - a falha vira linha do CSV
        status = f"error:{type(exc).__name__}"
    elapsed = time.perf_counter() - started
    return Sample(start_iso, now_iso(), elapsed, str(status), request_id), result


class TokenSource:
    """Token de acesso renovado a cada ``refresh_seconds``.

    O token do Keycloak dura poucos minutos; uma medicao longa (indexacao de 10 MB,
    reindexacao) passava a receber 401 e esperava ate o limite (ensaio da V7, 2026-10-21).
    """

    def __init__(self, fetch=None, refresh_seconds: float = 60.0, clock=time.monotonic) -> None:
        self._fetch = fetch or get_token
        self._refresh = refresh_seconds
        self._clock = clock
        self._token: str | None = None
        self._at = 0.0

    def __call__(self) -> str:
        now = self._clock()
        if self._token is None or now - self._at >= self._refresh:
            self._token, self._at = self._fetch(), now
        return self._token


def as_token_source(token):
    """Aceita o token fixo (testes) ou uma fonte que se renova."""
    return token if callable(token) else (lambda: token)


def api_headers(token: str, request_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers
