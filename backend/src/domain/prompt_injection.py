"""Verificador simples de injecao de prompt em trechos recuperados (RF-60).

Sinaliza padroes conhecidos; nao bloqueia a resposta. A defesa principal e
estrutural: os trechos vao delimitados, fora das instrucoes de sistema, e sao
tratados como dados (RN-31). O risco residual esta registrado como R16.
"""

from __future__ import annotations

import re
import unicodedata

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(
            r"\b(ignore|ignora|desconsidere|desconsidera|esqueca|esquece|disregard|forget)\w*"
            r"\s+(\w+\s+){0,3}"
            r"(instrucoes|instrucao|regras|orientacoes|instructions|rules|prompts?)\b"
        ),
    ),
    (
        "reveal_prompt",
        re.compile(
            r"\b(revele|revela|mostre|mostra|exiba|imprima|repita|reveal|show|print|repeat)"
            r"\s+(o\s+|seu\s+|the\s+|your\s+)*(prompt|instrucoes do sistema|system prompt|"
            r"system message|mensagem de sistema)"
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(voce agora e|a partir de agora,? voce|you are now|from now on,? you|"
            r"finja (ser|que)|pretend (to be|you are)|aja como se)\b"
        ),
    ),
    (
        "fake_delimiter",
        re.compile(r"<\s*/?\s*(system|trecho|assistant)\b|\[/?(inst|system)\]|^#{2,}\s*(system|instruc)", re.MULTILINE),
    ),
    (
        "new_instructions",
        re.compile(r"\b(novas instrucoes|new instructions|override (the )?system|system override)\b"),
    ),
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def detect_prompt_injection(text: str) -> tuple[str, ...]:
    """Nomes dos padroes encontrados no texto, sem repeticao."""
    normalized = _normalize(text)
    return tuple(name for name, pattern in _PATTERNS if pattern.search(normalized))
