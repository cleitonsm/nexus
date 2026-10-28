"""SPEC-013: parametros de recuperacao por assistente (CT-100 e a parte de dominio do CT-103)."""

from __future__ import annotations

import math
import unittest

from src.domain import (
    DomainValidationError,
    ParameterOrigin,
    RetrievalDefaults,
    RetrievalProfile,
)

ENVIRONMENT = RetrievalDefaults(
    hybrid_enabled=True, candidates=30, top_k=5, min_score=0.10
)


class RetrievalProfileRangesTestCase(unittest.TestCase):
    """CT-100 (D6): candidatos 5-100, top_k 1-20 e <= candidatos, limiar 0-1."""

    def test_empty_profile(self) -> None:
        profile = RetrievalProfile()
        self.assertTrue(profile.is_empty)
        self.assertEqual(profile.as_dict(), {})

    def test_limits_are_accepted(self) -> None:
        RetrievalProfile(candidates=5, top_k=1, min_score=0.0)
        RetrievalProfile(candidates=100, top_k=20, min_score=1.0)
        RetrievalProfile(hybrid_enabled=False)

    def test_out_of_range_values_are_rejected(self) -> None:
        cases = (
            {"candidates": 4},
            {"candidates": 101},
            {"top_k": 0},
            {"top_k": 21},
            {"min_score": -0.01},
            {"min_score": 1.01},
            {"min_score": math.nan},
            {"min_score": math.inf},
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(DomainValidationError):
                RetrievalProfile(**values)  # type: ignore[arg-type]

    def test_wrong_types_are_rejected(self) -> None:
        cases = (
            {"candidates": True},
            {"candidates": 10.5},
            {"candidates": "30"},
            {"top_k": False},
            {"min_score": True},
            {"min_score": "0.3"},
            {"hybrid_enabled": 1},
            {"hybrid_enabled": "false"},
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(DomainValidationError):
                RetrievalProfile(**values)  # type: ignore[arg-type]

    def test_integer_score_becomes_float(self) -> None:
        self.assertIsInstance(RetrievalProfile(min_score=1).min_score, float)

    def test_top_k_above_candidates_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            RetrievalProfile(candidates=10, top_k=11)
        RetrievalProfile(candidates=10, top_k=10)

    def test_as_dict_and_from_dict_round_trip(self) -> None:
        profile = RetrievalProfile(hybrid_enabled=False, top_k=8, min_score=0.3)
        stored = profile.as_dict()
        self.assertEqual(stored, {"hybrid_enabled": False, "top_k": 8, "min_score": 0.3})
        self.assertEqual(RetrievalProfile.from_dict(stored), profile)
        self.assertEqual(RetrievalProfile.from_dict(None), RetrievalProfile())

    def test_from_dict_rejects_unknown_fields(self) -> None:
        with self.assertRaises(DomainValidationError):
            RetrievalProfile.from_dict({"rerank_enabled": False})


class RetrievalProfileResolutionTestCase(unittest.TestCase):
    """RN-41 e T3/T4: valor do assistente vence o padrao; a origem acompanha."""

    def test_nothing_stored_returns_the_environment(self) -> None:
        resolved = RetrievalProfile().resolve(ENVIRONMENT)
        self.assertEqual(
            (resolved.hybrid_enabled, resolved.candidates, resolved.top_k, resolved.min_score),
            (True, 30, 5, 0.10),
        )
        for field_name in ("hybrid_enabled", "candidates", "top_k", "min_score"):
            self.assertEqual(resolved.origin(field_name), ParameterOrigin.DEFAULT)

    def test_stored_values_win_field_by_field(self) -> None:
        resolved = RetrievalProfile(min_score=0.3, hybrid_enabled=False).resolve(ENVIRONMENT)
        self.assertEqual(resolved.min_score, 0.3)
        self.assertFalse(resolved.hybrid_enabled)
        self.assertEqual(resolved.candidates, 30)
        self.assertEqual(resolved.origin("min_score"), ParameterOrigin.ASSISTANT)
        self.assertEqual(resolved.origin("hybrid_enabled"), ParameterOrigin.ASSISTANT)
        self.assertEqual(resolved.origin("candidates"), ParameterOrigin.DEFAULT)

    def test_saving_checks_top_k_against_effective_candidates(self) -> None:
        # T3: conferido ao gravar.
        narrow = RetrievalDefaults(hybrid_enabled=True, candidates=10, top_k=5, min_score=0.1)
        with self.assertRaises(DomainValidationError):
            RetrievalProfile(top_k=20).validate_against(narrow)
        with self.assertRaises(DomainValidationError):
            RetrievalProfile(candidates=5).validate_against(
                RetrievalDefaults(hybrid_enabled=True, candidates=30, top_k=8, min_score=0.1)
            )
        RetrievalProfile(top_k=10).validate_against(narrow)
        RetrievalProfile(min_score=0.3).validate_against(narrow)
        RetrievalProfile().validate_against(
            RetrievalDefaults(hybrid_enabled=True, candidates=5, top_k=8, min_score=0.1)
        )

    def test_question_time_never_fails_and_clamps_top_k(self) -> None:
        # O ambiente baixou os candidatos depois de o assistente gravar top_k=20.
        narrow = RetrievalDefaults(hybrid_enabled=True, candidates=10, top_k=5, min_score=0.1)
        resolved = RetrievalProfile(top_k=20).resolve(narrow)
        self.assertEqual((resolved.candidates, resolved.top_k), (10, 10))
        self.assertTrue(resolved.top_k_clamped)
        self.assertFalse(RetrievalProfile(top_k=8).resolve(narrow).top_k_clamped)

    def test_origins_are_read_only(self) -> None:
        resolved = RetrievalProfile().resolve(ENVIRONMENT)
        with self.assertRaises(TypeError):
            resolved.origins["min_score"] = ParameterOrigin.ASSISTANT  # type: ignore[index]

    def test_environment_values_skip_the_ranges(self) -> None:
        # T4: o ambiente de hoje continua valendo mesmo fora das faixas da D6.
        legacy = RetrievalDefaults(hybrid_enabled=True, candidates=200, top_k=30, min_score=0.5)
        resolved = RetrievalProfile().resolve(legacy)
        self.assertEqual((resolved.candidates, resolved.top_k), (200, 30))
        inverted = RetrievalDefaults(hybrid_enabled=True, candidates=5, top_k=8, min_score=0.1)
        self.assertEqual(RetrievalProfile().resolve(inverted).top_k, 8)

    def test_unknown_field_origin(self) -> None:
        with self.assertRaises(KeyError):
            RetrievalProfile().resolve(ENVIRONMENT).origin("rerank")


if __name__ == "__main__":
    unittest.main()
