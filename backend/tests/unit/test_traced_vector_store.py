"""SPEC-018: o rastreamento da busca repassa o escopo pessoal (RN-59).

Achado na validacao manual de 2026-10-30: o decorador recusava o argumento
novo e a pergunta ao resumidor respondia 500.
"""

from __future__ import annotations

import unittest
from contextlib import contextmanager

from src.domain import (
    SUMMARIZER_COLLECTION,
    CollectionName,
    ConversationId,
    PersonalScope,
    SparseVector,
)
from src.infrastructure.observability.instrumented import TracedVectorStore

SCOPE = PersonalScope(owner_user_id="ana", conversation_id=ConversationId("c1"))


class Span:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = dict(attributes)

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class Tracer:
    def __init__(self) -> None:
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, attributes: dict[str, object] | None = None):
        span = Span(attributes or {})
        self.spans.append(span)
        yield span


class Inner:
    def __init__(self) -> None:
        self.kwargs: list[dict[str, object]] = []

    def hybrid_search(self, *args, **kwargs):
        self.kwargs.append(kwargs)
        return []


class Legacy:
    """Adaptador sem o argumento novo: continua funcionando sem escopo."""

    def hybrid_search(self, collection_name, dense_vector, sparse_vector, limit,
                      payload_filter=None, *, user_groups):
        return []


class TracedVectorStoreTestCase(unittest.TestCase):
    def test_personal_scope_reaches_the_adapter_without_ids_in_the_span(self) -> None:
        tracer, inner = Tracer(), Inner()
        TracedVectorStore(inner, tracer).hybrid_search(
            SUMMARIZER_COLLECTION, [1.0], SparseVector(), 5,
            user_groups=frozenset(), personal_scope=SCOPE,
        )
        self.assertIs(inner.kwargs[0]["personal_scope"], SCOPE)
        attributes = tracer.spans[0].attributes
        self.assertIs(attributes["qdrant.personal_scope"], True)
        self.assertNotIn("ana", str(attributes))
        self.assertNotIn("c1", str(attributes))

    def test_without_scope_the_old_signature_still_works(self) -> None:
        traced = TracedVectorStore(Legacy(), Tracer())  # type: ignore[arg-type]
        self.assertEqual(
            traced.hybrid_search(CollectionName("assistant-rh"), [1.0], SparseVector(), 5,
                                 user_groups=frozenset()),
            [],
        )


if __name__ == "__main__":
    unittest.main()
