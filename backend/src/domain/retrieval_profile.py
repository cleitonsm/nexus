"""Parametros de recuperacao por assistente (SPEC-013, D1, D3 e D6).

Todos sao de consulta (RN-43): mudar nao exige reindexar. Campo vazio segue o
padrao global, que hoje vem do ambiente (RN-41). O reranker e os filtros de
seguranca (``user_groups`` e ``active``) nao sao configuraveis (D2, D3).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .errors import DomainValidationError

# D6: faixas aceitas para o que o assistente grava.
MIN_CANDIDATES = 5
MAX_CANDIDATES = 100
MIN_TOP_K = 1
MAX_TOP_K = 20
MIN_SCORE_FLOOR = 0.0
MIN_SCORE_CEILING = 1.0

PROFILE_FIELDS = ("hybrid_enabled", "candidates", "top_k", "min_score")


class ParameterOrigin(StrEnum):
    ASSISTANT = "assistant"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class RetrievalDefaults:
    """Padrao global; nao passa pelas faixas da D6 (T4)."""

    candidates: int
    top_k: int
    min_score: float
    hybrid_enabled: bool = True


@dataclass(frozen=True, slots=True)
class ResolvedRetrievalProfile:
    hybrid_enabled: bool
    candidates: int
    top_k: int
    min_score: float
    origins: Mapping[str, ParameterOrigin] = field(default_factory=dict)
    # O top_k gravado passou dos candidatos efetivos (o ambiente mudou depois
    # de gravar); a pergunta segue com top_k = candidatos e o chat registra.
    top_k_clamped: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "origins", MappingProxyType(dict(self.origins)))

    def origin(self, field_name: str) -> ParameterOrigin:
        return self.origins[field_name]


@dataclass(frozen=True, slots=True)
class RetrievalProfile:
    hybrid_enabled: bool | None = None
    candidates: int | None = None
    top_k: int | None = None
    min_score: float | None = None

    def __post_init__(self) -> None:
        if self.hybrid_enabled is not None and not isinstance(self.hybrid_enabled, bool):
            raise DomainValidationError("hybrid_enabled must be true or false.")
        _check_int(self.candidates, "candidates", MIN_CANDIDATES, MAX_CANDIDATES)
        _check_int(self.top_k, "top_k", MIN_TOP_K, MAX_TOP_K)
        if self.min_score is not None:
            object.__setattr__(self, "min_score", _checked_score(self.min_score))
        if (
            self.candidates is not None
            and self.top_k is not None
            and self.top_k > self.candidates
        ):
            raise DomainValidationError("top_k must not exceed candidates.")

    @property
    def is_empty(self) -> bool:
        return all(getattr(self, name) is None for name in PROFILE_FIELDS)

    def as_dict(self) -> dict[str, Any]:
        """So os campos gravados; e o formato persistido e auditado."""
        return {
            name: getattr(self, name)
            for name in PROFILE_FIELDS
            if getattr(self, name) is not None
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> RetrievalProfile:
        if not data:
            return cls()
        unknown = sorted(set(data) - set(PROFILE_FIELDS))
        if unknown:
            raise DomainValidationError(
                f"unknown retrieval settings: {', '.join(unknown)}."
            )
        return cls(**{name: data.get(name) for name in PROFILE_FIELDS})

    def validate_against(self, defaults: RetrievalDefaults) -> None:
        """T3, ao gravar: top_k efetivo <= candidatos efetivos.

        So vale quando o assistente grava um dos dois; o ambiente sozinho nao
        e conferido (T4).
        """
        if self.candidates is None and self.top_k is None:
            return
        candidates = defaults.candidates if self.candidates is None else self.candidates
        top_k = defaults.top_k if self.top_k is None else self.top_k
        if top_k > candidates:
            raise DomainValidationError(
                "effective top_k must not exceed effective candidates."
            )

    def resolve(self, defaults: RetrievalDefaults) -> ResolvedRetrievalProfile:
        """RN-41, a cada pergunta: valor do assistente vence o padrao.

        Nunca levanta erro: se o ambiente mudou depois de gravar e o top_k
        passou dos candidatos, usa top_k = candidatos e marca ``top_k_clamped``.
        """
        values: dict[str, Any] = {}
        origins: dict[str, ParameterOrigin] = {}
        for name in PROFILE_FIELDS:
            stored = getattr(self, name)
            if stored is None:
                values[name] = getattr(defaults, name)
                origins[name] = ParameterOrigin.DEFAULT
            else:
                values[name] = stored
                origins[name] = ParameterOrigin.ASSISTANT
        sizes_stored = self.candidates is not None or self.top_k is not None
        clamped = sizes_stored and values["top_k"] > values["candidates"]
        if clamped:
            values["top_k"] = values["candidates"]
        return ResolvedRetrievalProfile(origins=origins, top_k_clamped=clamped, **values)


def _check_int(value: object, name: str, minimum: int, maximum: int) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainValidationError(f"{name} must be an integer.")
    if not minimum <= value <= maximum:
        raise DomainValidationError(f"{name} must be between {minimum} and {maximum}.")


def _checked_score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainValidationError("min_score must be a number.")
    score = float(value)
    if math.isnan(score) or not MIN_SCORE_FLOOR <= score <= MIN_SCORE_CEILING:
        raise DomainValidationError(
            f"min_score must be between {MIN_SCORE_FLOOR} and {MIN_SCORE_CEILING}."
        )
    return score
