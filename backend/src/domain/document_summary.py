"""SPEC-018: resumidor de documentos (ADR 0014).

Regras puras do assistente de sistema que resume o documento pessoal do
usuario: limites (RN-60), lotes de secao (RN-63), tamanho do resumo (RN-62),
roteamento da mensagem (RN-61), etapas visiveis (D36) e o texto da finalidade
montado a partir das constantes (RF-119, D37). Nada aqui depende de framework,
de banco, do Qdrant ou do LLM; o texto do documento nao entra no dominio, so as
contagens de tokens.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

from .errors import DomainValidationError
from .value_objects import AssistantId, ConversationId

if TYPE_CHECKING:
    from .entities import Document, DocumentSummary

# --- Assistente de sistema (RF-112, D5) ------------------------------------

SUMMARIZER_SYSTEM_KIND: Final = "document_summarizer"
# T6 do plano: id fixo, o mesmo do INSERT da migracao 0013.
SUMMARIZER_ASSISTANT_ID: Final = AssistantId("system-document-summarizer")
SUMMARIZER_NAME: Final = "Resumidor de documentos"
SUMMARIZER_DESCRIPTION: Final = (
    "Resume documentos Word, PDF e texto enviados por você e responde perguntas "
    "sobre eles."
)

# --- Limites (RN-60) -------------------------------------------------------

MAX_SUMMARY_DOCUMENT_TOKENS: Final = 40_000  # D13
# So para o texto mostrado ao usuario: ~700 tokens por pagina densa em pt-BR.
PAGES_PER_40K_TOKENS_HINT: Final = "55 a 60"
SUMMARY_DOCUMENT_RETENTION: Final = timedelta(days=30)  # D9
DAILY_SUMMARY_DOCUMENTS: Final = 10  # D20
DAILY_SUMMARY_WINDOW: Final = timedelta(hours=24)

# --- Lotes de secao (D22, D23) ---------------------------------------------

SUMMARY_BATCH_TARGET_TOKENS: Final = 6_000
SUMMARY_BATCH_MIN_TOKENS: Final = 4_000
SUMMARY_BATCH_MAX_TOKENS: Final = 8_000

# --- Tamanho do resumo (D27) -----------------------------------------------

SUMMARY_MIN_WORDS: Final = 300
SUMMARY_MAX_WORDS: Final = 1_000
SUMMARY_TOKENS_PER_WORD_TARGET: Final = 40

# --- Codigos de falha mostrados na tela (D36) ------------------------------

DOCUMENT_TOO_LONG: Final = "document_too_long"
SUMMARY_FAILED: Final = "summary_failed"
PROCESSING_FAILED: Final = "processing_failed"


def _format_int(value: int) -> str:
    """Milhar com ponto, como em pt-BR (40.000)."""
    return f"{value:,}".replace(",", ".")


def exceeds_summary_token_limit(tokens: int) -> bool:
    """D15: o teto e inclusivo; acima dele o documento e recusado."""
    return tokens > MAX_SUMMARY_DOCUMENT_TOKENS


def document_too_long_message(tokens: int, limit: int = MAX_SUMMARY_DOCUMENT_TOKENS) -> str:
    return (
        f"O documento tem {_format_int(tokens)} tokens; "
        f"o limite é {_format_int(limit)}."
    )


def daily_summary_limit_reached(sent_last_24h: int, limit: int = DAILY_SUMMARY_DOCUMENTS) -> bool:
    """RN-60: conta todos os envios das ultimas 24 h, inclusive falhos e apagados."""
    return sent_last_24h >= limit


def summary_document_expires_at(uploaded_at: datetime) -> datetime:
    return uploaded_at + SUMMARY_DOCUMENT_RETENTION


# --- Escopo pessoal (RN-58, RN-59) -----------------------------------------


@dataclass(frozen=True, slots=True)
class PersonalScope:
    """Dono e conversa a que a busca no documento pessoal fica restrita.

    A busca so devolve trechos pessoais com este escopo; sem ele, trechos
    pessoais nunca voltam (falha fechada, ADR 0014 item 3).
    """

    owner_user_id: str
    conversation_id: ConversationId

    def __post_init__(self) -> None:
        owner = self.owner_user_id.strip()
        if not owner:
            raise DomainValidationError("personal scope owner must not be empty.")
        object.__setattr__(self, "owner_user_id", owner)


# --- Etapas (D36) ----------------------------------------------------------


class SummaryStage(StrEnum):
    UPLOADED = "enviado"
    EXTRACTING = "extraindo"
    INDEXING = "indexando"
    SUMMARIZING = "resumindo"
    READY = "pronto"
    FAILED = "falhou"
    EXPIRED = "expirado"


_BEFORE_INDEX: Final = frozenset(
    {SummaryStage.UPLOADED, SummaryStage.EXTRACTING, SummaryStage.INDEXING}
)


@dataclass(frozen=True, slots=True)
class SummaryProgress:
    """O que a tela mostra do documento da conversa (RF-115, D36).

    ``questions_available`` indica que a indexacao terminou e as perguntas
    pontuais ja podem ser respondidas (D21, D34), mesmo com o resumo em
    andamento ou falho (RN-64).
    """

    stage: SummaryStage
    done: int = 0
    total: int = 0
    failure_code: str | None = None
    failure_detail: str | None = None
    questions_available: bool = False

    def __post_init__(self) -> None:
        if self.done < 0 or self.total < 0:
            raise DomainValidationError("summary progress must not be negative.")
        if self.done > self.total:
            raise DomainValidationError("summary progress done must not pass total.")


def summary_progress(
    document: "Document",
    summary: "DocumentSummary | None",
) -> SummaryProgress:
    """Etapa visivel a partir do documento e do resumo gravado (D36, RN-64)."""
    from .entities import DocumentStatus

    if document.status is DocumentStatus.EXPIRED:
        return SummaryProgress(stage=SummaryStage.EXPIRED)
    if document.status is DocumentStatus.FAILED:
        code = summary.failure_code if summary and summary.failure_code else PROCESSING_FAILED
        return SummaryProgress(
            stage=SummaryStage.FAILED,
            failure_code=code,
            failure_detail=document.failure_reason,
        )
    if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        if summary is not None and summary.stage in _BEFORE_INDEX:
            return SummaryProgress(stage=summary.stage)
        if document.status is DocumentStatus.PENDING and document.attempts == 0:
            return SummaryProgress(stage=SummaryStage.UPLOADED)
        return SummaryProgress(stage=SummaryStage.EXTRACTING)
    # Indexado: perguntas liberadas; o resumo segue o registro gravado.
    if summary is None or summary.stage in _BEFORE_INDEX:
        return SummaryProgress(stage=SummaryStage.SUMMARIZING, questions_available=True)
    if summary.stage is SummaryStage.FAILED:
        return SummaryProgress(
            stage=SummaryStage.FAILED,
            failure_code=summary.failure_code or SUMMARY_FAILED,
            questions_available=True,
        )
    return SummaryProgress(
        stage=summary.stage,
        done=summary.batches_done,
        total=summary.batches_total,
        questions_available=True,
    )


# --- Lotes de secao (RN-63) ------------------------------------------------


@dataclass(frozen=True, slots=True)
class SectionTokens:
    """Secao do parser so com as contagens de tokens de cada paragrafo."""

    index: int
    title: str
    paragraph_tokens: tuple[int, ...]
    page_start: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "paragraph_tokens", tuple(self.paragraph_tokens))
        if self.index < 0:
            raise DomainValidationError("section index must not be negative.")
        if any(tokens < 0 for tokens in self.paragraph_tokens):
            raise DomainValidationError("paragraph tokens must not be negative.")

    @property
    def tokens(self) -> int:
        return sum(self.paragraph_tokens)


@dataclass(frozen=True, slots=True)
class BatchPiece:
    """Fatia de uma secao (paragrafos ``[paragraph_start, paragraph_end)``)."""

    section_index: int
    title: str
    paragraph_start: int
    paragraph_end: int
    tokens: int
    page_start: int | None = None


@dataclass(frozen=True, slots=True)
class SummaryBatch:
    pieces: tuple[BatchPiece, ...]

    @property
    def tokens(self) -> int:
        return sum(piece.tokens for piece in self.pieces)


def _section_pieces(section: SectionTokens) -> list[BatchPiece]:
    """Secao ate o maximo vira uma fatia; acima, fatias de ate ~6 mil por paragrafo."""
    def piece(start: int, end: int) -> BatchPiece:
        return BatchPiece(
            section_index=section.index,
            title=section.title,
            paragraph_start=start,
            paragraph_end=end,
            tokens=sum(section.paragraph_tokens[start:end]),
            page_start=section.page_start,
        )

    paragraphs = section.paragraph_tokens
    if section.tokens <= SUMMARY_BATCH_MAX_TOKENS:
        return [piece(0, len(paragraphs))]
    pieces: list[BatchPiece] = []
    start, running = 0, 0
    for position, tokens in enumerate(paragraphs):
        if running and running + tokens > SUMMARY_BATCH_TARGET_TOKENS:
            pieces.append(piece(start, position))
            start, running = position, 0
        running += tokens
    pieces.append(piece(start, len(paragraphs)))
    return pieces


def _fits_current(current: int, extra: int) -> bool:
    total = current + extra
    if total <= SUMMARY_BATCH_TARGET_TOKENS:
        return True
    # Lote abaixo do minimo pode passar do alvo, sem passar do maximo.
    return current < SUMMARY_BATCH_MIN_TOKENS and total <= SUMMARY_BATCH_MAX_TOKENS


def plan_summary_batches(sections: Sequence[SectionTokens]) -> tuple[SummaryBatch, ...]:
    """RN-63: secoes na ordem do documento em lotes de ~6 mil (4 a 8 mil) tokens.

    Cada paragrafo precisa chegar com no maximo ``SUMMARY_BATCH_MAX_TOKENS``
    (a infraestrutura divide o paragrafo enorme por frases antes). Documento
    abaixo do minimo e um lote unico (D19).
    """
    for section in sections:
        if any(tokens > SUMMARY_BATCH_MAX_TOKENS for tokens in section.paragraph_tokens):
            raise DomainValidationError(
                "split paragraphs above the batch maximum before planning."
            )
    pieces = [
        piece
        for section in sections
        if section.tokens > 0
        for piece in _section_pieces(section)
        if piece.tokens > 0
    ]
    if not pieces:
        raise DomainValidationError("document has no text to summarize.")
    batches: list[list[BatchPiece]] = []
    current: list[BatchPiece] = []
    running = 0
    for piece in pieces:
        if current and not _fits_current(running, piece.tokens):
            batches.append(current)
            current, running = [], 0
        current.append(piece)
        running += piece.tokens
    batches.append(current)
    if len(batches) > 1:
        last, previous = batches[-1], batches[-2]
        last_tokens = sum(piece.tokens for piece in last)
        previous_tokens = sum(piece.tokens for piece in previous)
        if (
            last_tokens < SUMMARY_BATCH_MIN_TOKENS
            and last_tokens + previous_tokens <= SUMMARY_BATCH_MAX_TOKENS
        ):
            batches[-2:] = [previous + last]
    return tuple(SummaryBatch(pieces=tuple(batch)) for batch in batches)


def plan_consolidation_groups(mini_summary_tokens: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    """D23: um grupo so ate o maximo; acima, grupos que cabem em 8 mil tokens.

    Devolve os indices dos mini-resumos de cada grupo, na ordem.
    """
    if any(tokens < 0 for tokens in mini_summary_tokens):
        raise DomainValidationError("mini summary tokens must not be negative.")
    indexes = tuple(range(len(mini_summary_tokens)))
    if sum(mini_summary_tokens) <= SUMMARY_BATCH_MAX_TOKENS:
        return (indexes,) if indexes else ()
    groups: list[tuple[int, ...]] = []
    current: list[int] = []
    running = 0
    for index, tokens in enumerate(mini_summary_tokens):
        if current and running + tokens > SUMMARY_BATCH_MAX_TOKENS:
            groups.append(tuple(current))
            current, running = [], 0
        current.append(index)
        running += tokens
    groups.append(tuple(current))
    return tuple(groups)


def target_summary_words(document_tokens: int) -> int:
    """RN-62: ``clamp(300, 1000, tokens / 40)``."""
    if document_tokens < 0:
        raise DomainValidationError("document tokens must not be negative.")
    proportional = document_tokens // SUMMARY_TOKENS_PER_WORD_TARGET
    return max(SUMMARY_MIN_WORDS, min(SUMMARY_MAX_WORDS, proportional))


# --- Roteamento da mensagem (RN-61) ----------------------------------------


class SummaryRequestKind(StrEnum):
    NONE = "none"
    GENERAL = "general"
    TAILORED = "tailored"


class SummarizerRoute(StrEnum):
    CAPABILITIES = "capabilities"
    PROGRESS = "progress"
    STORED_SUMMARY = "stored_summary"
    TAILORED_SUMMARY = "tailored_summary"
    QUESTION = "question"


_SUMMARY_PREFIXES: Final = ("resum", "sintetiz")
_SUMMARY_PHRASES: Final = (
    ("visao", "geral"),
    ("principais", "pontos"),
    ("pontos", "principais"),
)
# Palavras que nao recortam o pedido: ligacao, verbos de pedido e referencias
# ao proprio documento. Lista fechada (RN-61), coberta pelo CT-139.
_FILLER_WORDS: Final = frozenset(
    {
        "a", "as", "o", "os", "um", "uma", "uns", "umas",
        "de", "do", "da", "dos", "das", "deste", "desta", "desse", "dessa",
        "este", "esta", "esse", "essa", "isto", "isso", "aqui",
        "e", "em", "no", "na", "nos", "nas", "pra", "para", "pro", "por", "favor",
        "me", "mim", "voce", "vc", "pode", "poderia", "consegue",
        "quero", "queria", "gostaria", "preciso",
        "faca", "faz", "fazer", "gere", "gera", "gerar", "crie", "cria", "criar",
        "escreva", "escrever", "mostre", "mostra", "mostrar", "dar",
        "envie", "manda", "mande", "traga", "ver", "ter", "obter",
        "qual", "quais", "sao", "seria", "seriam",
        "documento", "arquivo", "texto", "conteudo", "anexo", "pdf", "word",
        "geral", "completo", "inteiro", "todo", "toda", "ai", "ok", "agora",
    }
)
_WORD: Final = re.compile(r"\w+")


def _words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return _WORD.findall(plain)


def classify_summary_request(text: str) -> SummaryRequestKind:
    """RN-61: geral, com recorte ou nenhum pedido de resumo."""
    words = _words(text)
    remaining = list(words)
    found = False
    for phrase in _SUMMARY_PHRASES:
        size = len(phrase)
        position = 0
        while position <= len(remaining) - size:
            if tuple(remaining[position : position + size]) == phrase:
                del remaining[position : position + size]
                found = True
            else:
                position += 1
    kept: list[str] = []
    for word in remaining:
        if word.startswith(_SUMMARY_PREFIXES):
            found = True
        else:
            kept.append(word)
    if not found:
        return SummaryRequestKind.NONE
    if all(word in _FILLER_WORDS for word in kept):
        return SummaryRequestKind.GENERAL
    return SummaryRequestKind.TAILORED


def route_summarizer_message(
    text: str,
    progress: SummaryProgress | None,
) -> SummarizerRoute:
    """RN-61: para onde vai a mensagem do usuario na conversa do resumidor."""
    if progress is None or progress.stage is SummaryStage.EXPIRED:
        return SummarizerRoute.CAPABILITIES
    if not progress.questions_available:
        return SummarizerRoute.PROGRESS
    kind = classify_summary_request(text)
    if kind is SummaryRequestKind.NONE:
        return SummarizerRoute.QUESTION
    if progress.stage is not SummaryStage.READY:
        return SummarizerRoute.PROGRESS
    if kind is SummaryRequestKind.GENERAL:
        return SummarizerRoute.STORED_SUMMARY
    return SummarizerRoute.TAILORED_SUMMARY


# --- Finalidade e especificacoes (RF-119, D37) -----------------------------

CapabilitiesReason = Literal["welcome", "no_document", "expired"]

_OPENINGS: Final[dict[str, str]] = {
    "welcome": "Olá! Eu sou o **{name}**: resumo documentos que você enviar e respondo perguntas sobre eles.",
    "no_document": "Para eu trabalhar, anexe um documento a esta conversa pelo clipe ao lado do campo de mensagem ou arrastando o arquivo.",
    "expired": "O documento desta conversa expirou e foi apagado. Para resumir outro, abra uma **Nova conversa** e anexe o arquivo.",
}


@dataclass(frozen=True, slots=True)
class SummarizerCapabilities:
    """Limites mostrados ao usuario; ``formats`` e ``max_bytes`` vem da ingestao."""

    formats: tuple[str, ...]
    max_bytes: int
    max_tokens: int = MAX_SUMMARY_DOCUMENT_TOKENS
    pages_hint: str = PAGES_PER_40K_TOKENS_HINT
    retention_days: int = SUMMARY_DOCUMENT_RETENTION.days
    daily_limit: int = DAILY_SUMMARY_DOCUMENTS
    out_of_scope: tuple[str, ...] = field(
        default=(
            "tabelas com a estrutura preservada (o conteúdo delas é lido como texto)",
            "comparar dois ou mais documentos",
        )
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "formats", tuple(self.formats))
        object.__setattr__(self, "out_of_scope", tuple(self.out_of_scope))
        if not self.formats:
            raise DomainValidationError("summarizer formats must not be empty.")
        if self.max_bytes <= 0 or self.max_tokens <= 0:
            raise DomainValidationError("summarizer limits must be positive.")
        if self.retention_days <= 0 or self.daily_limit < 0:
            raise DomainValidationError("summarizer retention and quota are invalid.")

    @property
    def max_megabytes_label(self) -> str:
        megabytes = self.max_bytes / (1024 * 1024)
        text = f"{megabytes:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text} MB"


def capabilities_markdown(
    capabilities: SummarizerCapabilities,
    *,
    reason: CapabilitiesReason,
) -> str:
    """RF-119: finalidade e limites, sem LLM; so a abertura muda com o motivo."""
    caps = capabilities
    opening = _OPENINGS[reason].format(name=SUMMARIZER_NAME)
    formats = ", ".join(caps.formats)
    lines = [
        opening,
        "",
        "**Como funciona**",
        "",
        "- Anexe **um documento por conversa**. Assim que ele for lido, você já pode fazer perguntas sobre ele.",
        "- O resumo aparece aqui sozinho quando fica pronto: visão geral, pontos principais por seção, "
        "números, datas e prazos, e conclusões, com a seção (e a página, em PDF) de cada ponto.",
        "- Depois, peça \"resuma\" para ver o resumo de novo, ou um recorte, como "
        "\"resuma em 5 tópicos\" ou \"resuma o capítulo 3\".",
        "",
        "**Especificações**",
        "",
        f"- Formatos aceitos: {formats}.",
        f"- Tamanho máximo do arquivo: {caps.max_megabytes_label}.",
        f"- Tamanho máximo do texto: {_format_int(caps.max_tokens)} tokens "
        f"(cerca de {caps.pages_hint} páginas de texto corrido).",
        "- PDF escaneado é lido por OCR e demora mais.",
        f"- Limite de {caps.daily_limit} documentos por dia.",
        f"- O documento fica guardado por {caps.retention_days} dias, ou até você excluir a conversa. "
        "Só você tem acesso a ele.",
        "- Para gerar o resumo, o texto do documento é enviado ao modelo de linguagem configurado no Nexus.",
        "",
        "**Ainda não faço**",
        "",
        *(f"- {item.capitalize()}." for item in caps.out_of_scope),
    ]
    return "\n".join(lines)
