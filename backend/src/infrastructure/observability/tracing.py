"""Rastreamento proprio, exportado por OTLP/HTTP em JSON (SPEC-006 D2, RF-56).

Sem SDK do OpenTelemetry: cada trecho e registrado em memoria e enviado em
lotes por uma thread ao coletor (``/v1/traces``). O identificador do
rastreamento e o da requisicao (``X-Request-ID``) quando ele tem o formato
do W3C; senao, o identificador vai como atributo ``nexus.request_id``
(RNF-29). Atributos passam por um filtro: nomes sensiveis sao descartados e
textos, truncados (RNF-25).
"""

from __future__ import annotations

import json
import logging
import queue
import re
import secrets
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from urllib import error, request

from src.domain import AttributeValue, MetricsRecorder

from .structured_logging import get_request_id

logger = logging.getLogger(__name__)

_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
# Atributos com estes nomes (ou partes de nome) nunca saem do processo (RNF-25).
_FORBIDDEN_PARTS = frozenset(
    {
        "apikey",
        "authorization",
        "answer",
        "comment",
        "content",
        "credential",
        "excerpt",
        "key",
        "password",
        "prompt",
        "question",
        "secret",
        "text",
        "token",
    }
)
_NAME_PARTS = re.compile(r"[._\-]+")
_MAX_ATTRIBUTE_LENGTH = 120
_MAX_ATTRIBUTES = 32
_CLIENT_PREFIXES = ("llm.", "qdrant.", "keycloak.")


@dataclass(slots=True)
class SpanRecord:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_ns: int
    end_ns: int = 0
    attributes: dict[str, AttributeValue] = field(default_factory=dict)
    error_type: str | None = None

    @property
    def duration_seconds(self) -> float:
        return max(self.end_ns - self.start_ns, 0) / 1e9

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        clean = sanitize_attribute(key, value)
        if clean is not None and (
            key in self.attributes or len(self.attributes) < _MAX_ATTRIBUTES
        ):
            self.attributes[key] = clean

    def record_error(self, error: BaseException) -> None:
        # So o tipo: a mensagem pode carregar texto do provedor ou do usuario.
        self.error_type = type(error).__name__


def sanitize_attribute(key: str, value: object) -> AttributeValue | None:
    if not key or forbidden_attribute(key):
        return None
    if isinstance(value, bool | int | float):
        return value
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) > _MAX_ATTRIBUTE_LENGTH:
        text = text[:_MAX_ATTRIBUTE_LENGTH] + "..."
    return text


def forbidden_attribute(key: str) -> bool:
    return any(part in _FORBIDDEN_PARTS for part in _NAME_PARTS.split(key.lower()))


_current_span: ContextVar[SpanRecord | None] = ContextVar(
    "nexus_current_span", default=None
)


def current_span() -> SpanRecord | None:
    return _current_span.get()


class SpanTracer:
    """Implementacao da porta ``Tracer``.

    O trecho atual fica num ``ContextVar``. Ao sair, o anterior e restaurado
    por valor, e nao por token: o streaming retoma o gerador em contextos
    copiados a cada parte, onde um token nao seria aceito.
    """

    def __init__(
        self,
        *,
        exporter: OtlpJsonSpanExporter | None = None,
        metrics: MetricsRecorder | None = None,
        id_source: Callable[[int], str] = secrets.token_hex,
        clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self._exporter = exporter
        self._metrics = metrics
        self._id_source = id_source
        self._clock_ns = clock_ns

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, AttributeValue] | None = None,
    ) -> Iterator[SpanRecord]:
        parent = _current_span.get()
        record = SpanRecord(
            name=name,
            trace_id=parent.trace_id if parent else self._new_trace_id(),
            span_id=self._id_source(8),
            parent_span_id=parent.span_id if parent else None,
            start_ns=self._clock_ns(),
        )
        request_id = get_request_id()
        if request_id:
            record.set_attribute("nexus.request_id", request_id)
        for key, value in (attributes or {}).items():
            record.set_attribute(key, value)
        _current_span.set(record)
        try:
            yield record
        except Exception as exc:
            record.record_error(exc)
            raise
        finally:
            record.end_ns = self._clock_ns()
            _current_span.set(parent)
            self._finish(record)

    def _new_trace_id(self) -> str:
        request_id = (get_request_id() or "").lower()
        if _TRACE_ID.fullmatch(request_id) and request_id != "0" * 32:
            return request_id
        return self._id_source(16)

    def _finish(self, record: SpanRecord) -> None:
        if self._metrics is not None:
            self._metrics.observe(
                "nexus_stage_duration_seconds",
                record.duration_seconds,
                {"stage": record.name},
            )
        if self._exporter is not None:
            self._exporter.submit(record)


def span_kind(name: str) -> int:
    """OTLP: 1 interno, 2 servidor, 3 cliente."""
    if name.startswith("http."):
        return 2
    if name.startswith(_CLIENT_PREFIXES):
        return 3
    return 1


def to_otlp_json(records: list[SpanRecord], service_name: str) -> dict[str, object]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [_attribute("service.name", service_name)]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "nexus"},
                        "spans": [_span_json(record) for record in records],
                    }
                ],
            }
        ]
    }


def _span_json(record: SpanRecord) -> dict[str, object]:
    span: dict[str, object] = {
        "traceId": record.trace_id,
        "spanId": record.span_id,
        "name": record.name,
        "kind": span_kind(record.name),
        "startTimeUnixNano": str(record.start_ns),
        "endTimeUnixNano": str(record.end_ns),
        "attributes": [
            _attribute(key, value) for key, value in sorted(record.attributes.items())
        ],
        "status": {"code": 2 if record.error_type else 1},
    }
    if record.parent_span_id:
        span["parentSpanId"] = record.parent_span_id
    if record.error_type:
        span["attributes"].append(_attribute("error.type", record.error_type))  # type: ignore[union-attr]
    return span


def _attribute(key: str, value: AttributeValue) -> dict[str, object]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


class OtlpJsonSpanExporter:
    """Envia lotes de trechos ao coletor; nunca bloqueia a requisicao.

    Fila cheia ou coletor fora do ar: os trechos sao descartados e contados.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        service_name: str,
        batch_size: int = 64,
        flush_interval_seconds: float = 2.0,
        max_queue: int = 2048,
        timeout_seconds: float = 3.0,
        sender: Callable[[str, bytes, float], None] | None = None,
        start_thread: bool = True,
    ) -> None:
        self._url = endpoint.rstrip("/") + "/v1/traces"
        self._service_name = service_name
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._timeout = timeout_seconds
        self._queue: queue.Queue[SpanRecord] = queue.Queue(maxsize=max_queue)
        self._send = sender or _post_json
        self.dropped = 0
        self._failures = 0
        if start_thread:
            threading.Thread(
                target=self._run, name="nexus-otlp-exporter", daemon=True
            ).start()

    def submit(self, record: SpanRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1

    def flush(self) -> int:
        """Envia o que estiver na fila; devolve quantos trechos saiu."""
        batch: list[SpanRecord] = []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._export(batch)
        return len(batch)

    def _run(self) -> None:
        while True:
            time.sleep(self._flush_interval)
            while self.flush() == self._batch_size:
                continue

    def _export(self, batch: list[SpanRecord]) -> None:
        body = json.dumps(to_otlp_json(batch, self._service_name)).encode("utf-8")
        try:
            self._send(self._url, body, self._timeout)
        except (OSError, ValueError) as exc:
            self.dropped += len(batch)
            self._failures += 1
            # Um aviso a cada 100 falhas: o coletor e opcional (perfil D1).
            if self._failures % 100 == 1:
                logger.warning(
                    "tracing.export.failed",
                    extra={"error_type": type(exc).__name__, "dropped": self.dropped},
                )
        else:
            self._failures = 0


def _post_json(url: str, body: bytes, timeout: float) -> None:
    http_request = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            response.read()
    except error.HTTPError as exc:
        raise OSError(f"collector answered {exc.code}") from exc
