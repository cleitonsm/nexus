from __future__ import annotations

import json
from pathlib import Path

from src.domain import DomainValidationError, EvaluationItem


class EvaluationDatasetError(ValueError):
    """Conjunto de referencia invalido; `errors` lista cada problema."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"invalid evaluation dataset: {len(errors)} problem(s).")
        self.errors = errors


class JsonlEvaluationDatasetLoader:
    """Le um conjunto de referencia em JSON Lines, um item por linha."""

    def __init__(self, *, allow_unvalidated: bool = False) -> None:
        self._allow_unvalidated = allow_unvalidated

    def load(self, path: Path) -> list[EvaluationItem]:
        items: list[EvaluationItem] = []
        errors: list[str] = []
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                items.append(self._parse(line))
            except (ValueError, TypeError) as exc:
                errors.append(f"linha {number}: {exc}")
        errors.extend(_duplicated_ids(items))
        if not items and not errors:
            errors.append("o conjunto de referencia esta vazio.")
        if errors:
            raise EvaluationDatasetError(errors)
        return items

    def _parse(self, line: str) -> EvaluationItem:
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError("cada linha deve ser um objeto JSON.")
        try:
            item = _to_item(raw)
        except DomainValidationError as exc:
            raise ValueError(str(exc)) from exc
        if not item.is_validated and not self._allow_unvalidated:
            raise ValueError(
                f"item '{item.id}' nao foi validado por um curador (validated_by)."
            )
        return item


def _to_item(raw: dict[str, object]) -> EvaluationItem:
    sources = raw.get("source_documents") or []
    if not isinstance(sources, list):
        raise ValueError("source_documents deve ser uma lista.")
    return EvaluationItem(
        id=str(raw.get("id") or ""),
        question=str(raw.get("question") or ""),
        expected_answer=_optional_text(raw.get("expected_answer")),
        source_documents=tuple(str(name) for name in sources),
        out_of_scope=raw.get("out_of_scope") is True,
        validated_by=_optional_text(raw.get("validated_by")),
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _duplicated_ids(items: list[EvaluationItem]) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        if item.id in seen:
            errors.append(f"id duplicado: '{item.id}'.")
        seen.add(item.id)
    return errors
