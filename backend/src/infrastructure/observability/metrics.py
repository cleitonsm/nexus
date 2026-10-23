"""Metricas em memoria no formato de texto do Prometheus (SPEC-006 D2, RF-57).

Sem ``prometheus-client``: contadores e histogramas por nome e rotulos, mais
coletores que leem valores na hora da coleta (jobs de ingestao por estado,
lidos do banco, para que o worker nao precise expor metricas proprias).
Rotulos so recebem valores de baixa cardinalidade e sem texto de usuario.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

LabelKey = tuple[tuple[str, str], ...]

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

HELP = {
    "nexus_http_requests_total": "Requisicoes HTTP por metodo, rota e status.",
    "nexus_http_request_duration_seconds": "Duracao das requisicoes HTTP.",
    "nexus_stage_duration_seconds": "Duracao de cada etapa rastreada (no do grafo ou chamada externa).",
    "nexus_chat_questions_total": "Perguntas ao chat por resultado (answered, fallback, failed, cancelled).",
    "nexus_chat_time_to_first_token_seconds": "Tempo ate a primeira parte da resposta em streaming (RNF-01).",
    "nexus_llm_tokens_total": "Tokens do LLM por direcao (input, output).",
    "nexus_llm_estimated_cost_total": "Custo estimado do LLM; estimativa pela tabela de precos, nao fatura.",
    "nexus_prompt_injection_suspected_total": "Trechos recuperados com padrao de injecao de prompt (RF-60).",
    "nexus_usage_limit_blocked_total": "Perguntas recusadas pelo limite de uso, por janela (RN-32).",
    "nexus_ingestion_jobs": "Jobs de ingestao por estado, lidos do banco na coleta.",
    "nexus_feedback_total": "Avaliacoes de resposta por nota.",
}


@dataclass(frozen=True, slots=True)
class GaugeSample:
    name: str
    labels: Mapping[str, str]
    value: float


GaugeCollector = Callable[[], Iterable[GaugeSample]]


class _Histogram:
    __slots__ = ("buckets", "counts", "sum", "count")

    def __init__(self, buckets: tuple[float, ...]) -> None:
        self.buckets = buckets
        self.counts = [0] * len(buckets)
        self.sum = 0.0
        self.count = 0

    def observe(self, value: float) -> None:
        self.sum += value
        self.count += 1
        for index, bound in enumerate(self.buckets):
            if value <= bound:
                self.counts[index] += 1


class MetricsRegistry:
    """Implementacao da porta ``MetricsRecorder``; segura entre threads."""

    def __init__(self, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        self._buckets = buckets
        self._lock = threading.Lock()
        self._counters: dict[str, dict[LabelKey, float]] = {}
        self._histograms: dict[str, dict[LabelKey, _Histogram]] = {}
        self._collectors: list[GaugeCollector] = []

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if value < 0 or math.isnan(value):
            return
        key = _label_key(labels)
        with self._lock:
            series = self._counters.setdefault(name, {})
            series[key] = series.get(key, 0.0) + value

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if math.isnan(value):
            return
        key = _label_key(labels)
        with self._lock:
            series = self._histograms.setdefault(name, {})
            histogram = series.get(key)
            if histogram is None:
                histogram = series[key] = _Histogram(self._buckets)
            histogram.observe(value)

    def register_collector(self, collector: GaugeCollector) -> None:
        self._collectors.append(collector)

    def render(self) -> str:
        """Formato de exposicao em texto 0.0.4 do Prometheus."""
        lines: list[str] = []
        with self._lock:
            counters = {name: dict(series) for name, series in self._counters.items()}
            histograms = {
                name: {key: _copy(item) for key, item in series.items()}
                for name, series in self._histograms.items()
            }
        for name in sorted(counters):
            _header(lines, name, "counter")
            for key, value in sorted(counters[name].items()):
                lines.append(f"{name}{_labels(key)} {_number(value)}")
        for name in sorted(histograms):
            _header(lines, name, "histogram")
            for key, histogram in sorted(histograms[name].items()):
                _histogram_lines(lines, name, key, histogram)
        _gauge_lines(lines, self._collect())
        return "\n".join(lines) + "\n"

    def _collect(self) -> list[GaugeSample]:
        samples: list[GaugeSample] = []
        for collector in self._collectors:
            try:
                samples.extend(collector())
            except Exception:  # noqa: BLE001 - coleta falha, /metrics continua
                continue
        return samples


def _copy(histogram: _Histogram) -> _Histogram:
    copy = _Histogram(histogram.buckets)
    copy.counts = list(histogram.counts)
    copy.sum = histogram.sum
    copy.count = histogram.count
    return copy


def _histogram_lines(
    lines: list[str],
    name: str,
    key: LabelKey,
    histogram: _Histogram,
) -> None:
    for bound, count in zip(histogram.buckets, histogram.counts, strict=True):
        bucket_key = (*key, ("le", _number(bound)))
        lines.append(f"{name}_bucket{_labels(bucket_key)} {count}")
    lines.append(f"{name}_bucket{_labels((*key, ('le', '+Inf')))} {histogram.count}")
    lines.append(f"{name}_sum{_labels(key)} {_number(histogram.sum)}")
    lines.append(f"{name}_count{_labels(key)} {histogram.count}")


def _gauge_lines(lines: list[str], samples: list[GaugeSample]) -> None:
    by_name: dict[str, list[GaugeSample]] = {}
    for sample in samples:
        by_name.setdefault(sample.name, []).append(sample)
    for name in sorted(by_name):
        _header(lines, name, "gauge")
        for sample in by_name[name]:
            lines.append(
                f"{name}{_labels(_label_key(sample.labels))} {_number(sample.value)}"
            )


def _header(lines: list[str], name: str, kind: str) -> None:
    lines.append(f"# HELP {name} {HELP.get(name, name)}")
    lines.append(f"# TYPE {name} {kind}")


def _label_key(labels: Mapping[str, str] | None) -> LabelKey:
    return tuple(sorted((str(k), str(v)) for k, v in (labels or {}).items()))


def _labels(key: LabelKey) -> str:
    if not key:
        return ""
    body = ",".join(f'{name}="{_escape(value)}"' for name, value in key)
    return "{" + body + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))
