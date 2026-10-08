"""Portas de rastreamento e de metricas (SPEC-006 D2, RF-56, RF-57).

O dominio e a aplicacao so conhecem estas portas; a exportacao OTLP e o
formato do Prometheus ficam na infraestrutura. Atributos e rotulos nunca
levam texto de documentos, perguntas, respostas, tokens ou chaves (RNF-25).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol

AttributeValue = str | int | float | bool


class Span(Protocol):
    def set_attribute(self, key: str, value: AttributeValue) -> None: ...

    def record_error(self, error: BaseException) -> None: ...


class Tracer(Protocol):
    def span(
        self,
        name: str,
        attributes: Mapping[str, AttributeValue] | None = None,
    ) -> AbstractContextManager[Span]:
        """Trecho filho do trecho atual; o erro que escapar fica registrado."""
        ...


class MetricsRecorder(Protocol):
    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None: ...


class _NoopSpan:
    def set_attribute(self, key: str, value: AttributeValue) -> None:
        return None

    def record_error(self, error: BaseException) -> None:
        return None


class NoopTracer:
    """Usado quando nenhum rastreamento foi configurado (e nos testes)."""

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, AttributeValue] | None = None,
    ) -> Iterator[Span]:
        yield _NoopSpan()


class NoopMetrics:
    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        return None

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        return None
