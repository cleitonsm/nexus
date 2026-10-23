from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import logging
import time
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from src.application.dto import ChatStreamEvent, ChatTurnResult, MessageDTO
from src.application.services import (
    DEFAULT_ANSWER_INSTRUCTION,
    AccessControl,
    ContextRetriever,
    GroundedAnswerGenerator,
    UsageGovernance,
    fit_context,
    trim_history,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    ChatMessage,
    Citation,
    ContextChunk,
    ConversationId,
    ConversationRepository,
    MessageId,
    MessageRole,
    MetricsRecorder,
    NoopMetrics,
    NoopTracer,
    SearchResult,
    TokenCounter,
    TokenUsage,
    Tracer,
    UsageLimitExceededError,
    detect_prompt_injection,
)

__all__ = [
    "DEFAULT_ANSWER_INSTRUCTION",
    "ChatWithAssistantInput",
    "ChatWithAssistantUseCase",
    "ConversationNotFoundError",
]

ChatNode = Callable[["ChatState"], "ChatState"]


class ConversationNotFoundError(ValueError):
    pass


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChatWithAssistantInput:
    user: AuthenticatedUser
    conversation_id: str
    question: str
    # Teto por pergunta: pede menos trechos que RERANK_TOP_N, nunca mais.
    top_k: int | None = None
    fallback_answer: str = (
        "Nao encontrei contexto suficiente nos documentos deste assistente "
        "para responder com seguranca."
    )


class ChatState(TypedDict):
    user: AuthenticatedUser
    conversation_id: ConversationId
    assistant_id: AssistantId
    question: str
    # Grupos de quem pergunta: filtro obrigatorio da busca (RF-43).
    user_groups: frozenset[str]
    top_n: int
    fallback_answer: str
    assistant_initial_prompt: str | None
    conversation_history: list[ChatMessage]
    user_message: ChatMessage
    search_query: str
    candidates: list[SearchResult]
    ranked: list[SearchResult]
    relevant: list[SearchResult]
    context_chunks: list[ContextChunk]
    citations: tuple[Citation, ...]
    fallback_used: bool
    answer: str
    assistant_message: ChatMessage
    # Tokens das chamadas ao LLM desta pergunta (RF-57).
    usage: TokenUsage
    # Trechos com padrao de injecao de prompt (RF-60); so sinalizados.
    injection_flags: int


class ChatWithAssistantUseCase:
    """Grafo conversacional da SPEC-003.

    historico -> pergunta -> reescrita -> busca hibrida -> reranking ->
    nota minima -> orcamento -> geracao -> validacao das citacoes -> gravacao.
    Sem trecho acima da nota minima, ou sem citacao valida, vale o fallback.

    SPEC-004: a conversa precisa ser de quem pergunta (RN-24), o assistente
    precisa estar ao alcance dos seus grupos (RF-42) e a busca so devolve
    documentos que esses grupos podem ler (RF-43). Cada pergunta fica na
    auditoria com os documentos recuperados, sem texto algum (RF-45).
    """

    def __init__(
        self,
        *,
        assistant_repository: AssistantRepository,
        conversation_repository: ConversationRepository,
        context_retriever: ContextRetriever,
        answer_generator: GroundedAnswerGenerator,
        token_counter: TokenCounter,
        access_control: AccessControl,
        usage_governance: UsageGovernance | None = None,
        tracer: Tracer | None = None,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._access = access_control
        self._usage = usage_governance
        self._tracer = tracer or NoopTracer()
        self._metrics = metrics or NoopMetrics()
        self._assistant_repository = assistant_repository
        self._conversation_repository = conversation_repository
        self._retriever = context_retriever
        self._answer_generator = answer_generator
        self._token_counter = token_counter
        self._ranked_so_far: list[SearchResult] = []
        self._usage_so_far = TokenUsage()
        self._graph = self._build_graph()
        self._prepare_graph = self._build_prepare_graph()
        self._finalize_graph = self._build_finalize_graph()

    def execute(self, data: ChatWithAssistantInput) -> ChatTurnResult:
        initial_state = self._start(data)
        with self._tracer.span("chat.turn", _turn_attributes(initial_state, "sync")):
            try:
                final_state = self._graph.invoke(initial_state)
            except Exception as exc:
                self._finish_failure(initial_state, exc, mode="sync")
                raise
        return self._finish_success(final_state, mode="sync")

    def start_stream(self, data: ChatWithAssistantInput) -> Iterator[ChatStreamEvent]:
        """RF-58: valida ja (404, 403, 429) e devolve os eventos da resposta.

        O texto chega em partes; a validacao das citacoes (RN-18) ocorre ao
        final e, se reprovar, um evento ``replace`` troca o texto pelo
        fallback. O ultimo evento e ``done``, com as citacoes.
        """
        initial_state = self._start(data)
        return self._stream_events(initial_state)

    def _start(self, data: ChatWithAssistantInput) -> ChatState:
        question = data.question.strip()
        if not question:
            raise ValueError("question must not be empty.")

        conversation_id = ConversationId(data.conversation_id)
        conversation = self._conversation_repository.get_by_id(conversation_id)
        if conversation is None or not self._access.owns_conversation(
            data.user, conversation.owner_user_id
        ):
            raise ConversationNotFoundError("conversation not found.")
        self._access.require_assistant_access(
            data.user,
            conversation.assistant_id,
            AuditAction.CHAT_QUESTION,
        )
        self._check_usage_limit(data.user, conversation_id, conversation.assistant_id)
        assistant = self._assistant_repository.get_by_id(
            conversation.assistant_id
        )

        # Trechos ja ranqueados e tokens ja gastos: se a pergunta falhar
        # depois, a auditoria e o consumo ainda registram o que houve (C9).
        self._ranked_so_far = []
        self._usage_so_far = TokenUsage()
        return self._initial_state(
            data, conversation_id, conversation.assistant_id, question, assistant
        )

    def _check_usage_limit(
        self,
        user: AuthenticatedUser,
        conversation_id: ConversationId,
        assistant_id: AssistantId,
    ) -> None:
        if self._usage is None:
            return
        try:
            self._usage.check(user)
        except UsageLimitExceededError as exc:
            self._access.audit(
                user,
                AuditAction.CHAT_RATE_LIMITED,
                resource_type=AuditResource.ASSISTANT,
                resource_id=assistant_id.value,
                details={
                    "assistant_id": assistant_id.value,
                    "conversation_id": conversation_id.value,
                    "window": exc.window,
                    "limit": exc.limit,
                    "retry_at": exc.retry_at.isoformat(),
                },
            )
            raise

    def _stream_events(self, initial_state: ChatState) -> Iterator[ChatStreamEvent]:
        finished = False
        with self._tracer.span("chat.turn", _turn_attributes(initial_state, "stream")):
            try:
                state = self._prepare_graph.invoke(initial_state)
                streamed = ""
                if not state["fallback_used"]:
                    streamed, state = yield from self._stream_answer(state)
                state = self._finalize_graph.invoke(state)
                finished = True
            except GeneratorExit:
                # O cliente desconectou: a pergunta conta e o consumo fica.
                self._finish_failure(initial_state, None, mode="stream")
                raise
            except Exception as exc:
                self._finish_failure(initial_state, exc, mode="stream")
                raise
        if finished:
            result = self._finish_success(state, mode="stream")
            if state["answer"] != streamed.strip():
                yield ChatStreamEvent(kind="replace", text=state["answer"])
            yield ChatStreamEvent(kind="done", result=result)

    def _stream_answer(self, state: ChatState):
        """No ``generate_answer`` do grafo, executado fora dele para transmitir."""
        parts: list[str] = []
        usage = TokenUsage()
        started_at = time.perf_counter()
        with self._tracer.span("chat.generate_answer", {"graph.node": "generate_answer"}):
            for chunk in self._answer_generator.generate_stream(
                question=state["question"],
                context_chunks=state["context_chunks"],
                history=state["conversation_history"],
                instruction=state["assistant_initial_prompt"],
            ):
                if chunk.usage is not None:
                    usage = usage + chunk.usage
                    self._usage_so_far = state["usage"] + usage
                if not chunk.text:
                    continue
                if not parts:
                    self._metrics.observe(
                        "nexus_chat_time_to_first_token_seconds",
                        time.perf_counter() - started_at,
                    )
                parts.append(chunk.text)
                yield ChatStreamEvent(kind="delta", text=chunk.text)
        streamed = "".join(parts)
        return streamed, {
            **state,
            "answer": streamed.strip(),
            "usage": state["usage"] + usage,
        }

    def _finish_success(self, final_state: ChatState, *, mode: str) -> ChatTurnResult:
        fallback_used = final_state["fallback_used"]
        self._audit_question(final_state["user"], final_state)
        self._record_usage(
            final_state["user"],
            final_state["conversation_id"],
            final_state["assistant_id"],
            final_state["usage"],
            fallback_used=fallback_used,
            failed=False,
        )
        self._metrics.increment(
            "nexus_chat_questions_total",
            labels={
                "mode": mode,
                "outcome": "fallback" if fallback_used else "answered",
            },
        )
        return ChatTurnResult(
            conversation_id=final_state["conversation_id"].value,
            assistant_id=final_state["assistant_id"].value,
            user_message=MessageDTO.from_entity(final_state["user_message"]),
            assistant_message=MessageDTO.from_entity(
                final_state["assistant_message"]
            ),
            used_context_chunks=(
                0 if fallback_used else len(final_state["context_chunks"])
            ),
            fallback_used=fallback_used,
            rewritten_query=final_state["search_query"],
        )

    def _finish_failure(
        self,
        initial_state: ChatState,
        error: Exception | None,
        *,
        mode: str,
    ) -> None:
        user = initial_state["user"]
        self._audit_failure(
            user,
            initial_state["conversation_id"],
            initial_state["assistant_id"],
            type(error).__name__ if error is not None else "ClientDisconnected",
        )
        self._record_usage(
            user,
            initial_state["conversation_id"],
            initial_state["assistant_id"],
            self._usage_so_far,
            fallback_used=False,
            failed=True,
        )
        self._metrics.increment(
            "nexus_chat_questions_total",
            labels={
                "mode": mode,
                "outcome": "failed" if error is not None else "cancelled",
            },
        )

    def _record_usage(
        self,
        user: AuthenticatedUser,
        conversation_id: ConversationId,
        assistant_id: AssistantId,
        usage: TokenUsage,
        *,
        fallback_used: bool,
        failed: bool,
    ) -> None:
        if self._usage is None:
            return
        try:
            self._usage.record(
                user,
                conversation_id=conversation_id.value,
                assistant_id=assistant_id.value,
                usage=usage,
                fallback_used=fallback_used,
                failed=failed,
            )
        except Exception as exc:  # noqa: BLE001 - consumo nao derruba a resposta
            logger.warning(
                "chat.usage.record_failed",
                extra={"error_type": type(exc).__name__},
            )

    def _initial_state(
        self,
        data: ChatWithAssistantInput,
        conversation_id: ConversationId,
        assistant_id: AssistantId,
        question: str,
        assistant: Assistant | None,
    ) -> ChatState:
        return {  # type: ignore[typeddict-item]
            "user": data.user,
            "conversation_id": conversation_id,
            "assistant_id": assistant_id,
            "question": question,
            "user_groups": data.user.groups,
            "top_n": self._top_n(data.top_k),
            "fallback_answer": data.fallback_answer,
            "assistant_initial_prompt": (
                assistant.initial_prompt if assistant else None
            ),
            "usage": TokenUsage(),
            "injection_flags": 0,
        }

    def _audit_failure(
        self,
        user: AuthenticatedUser,
        conversation_id: ConversationId,
        assistant_id: AssistantId,
        error_type: str,
    ) -> None:
        """C9: pergunta interrompida tambem entra na trilha, marcada como falha."""
        self._access.audit(
            user,
            AuditAction.CHAT_QUESTION,
            resource_type=AuditResource.ASSISTANT,
            resource_id=assistant_id.value,
            details={
                "assistant_id": assistant_id.value,
                "conversation_id": conversation_id.value,
                "failed": True,
                "error_type": error_type,
                "retrieved_documents": _retrieved(self._ranked_so_far),
                "cited_documents": [],
            },
        )

    def _audit_question(self, user: AuthenticatedUser, state: ChatState) -> None:
        """So identificadores: nem a pergunta nem os trechos entram na trilha."""
        self._access.audit(
            user,
            AuditAction.CHAT_QUESTION,
            resource_type=AuditResource.ASSISTANT,
            resource_id=state["assistant_id"].value,
            details={
                "assistant_id": state["assistant_id"].value,
                "conversation_id": state["conversation_id"].value,
                "fallback_used": state["fallback_used"],
                "failed": False,
                "retrieved_documents": _retrieved(state["ranked"]),
                "cited_documents": sorted(
                    {item.document_id.value for item in state["citations"]}
                ),
            },
        )

    def _top_n(self, top_k: int | None) -> int:
        configured = self._retriever.settings.top_n
        if top_k is None:
            return configured
        return max(min(top_k, configured), 1)

    def _build_graph(self):
        """Grafo completo, da pergunta a gravacao (rota sem streaming)."""
        graph = StateGraph(ChatState)
        self._add_preparation(graph)
        self._add_node(graph, "generate_answer", self._generate_answer)
        self._add_finalization(graph)
        graph.set_entry_point("load_conversation_history")
        graph.add_conditional_edges(
            "evaluate_context",
            self._next_after_evaluation,
            {
                "build_context": "build_context",
                "fallback_answer": "fallback_answer",
            },
        )
        graph.add_edge("build_context", "generate_answer")
        graph.add_edge("generate_answer", "validate_citations")
        return graph.compile()

    def _build_prepare_graph(self):
        """Streaming, parte 1: ate o contexto montado, ou o fallback decidido."""
        graph = StateGraph(ChatState)
        self._add_preparation(graph)
        graph.set_entry_point("load_conversation_history")
        graph.add_conditional_edges(
            "evaluate_context",
            self._next_after_evaluation,
            {"build_context": "build_context", "fallback_answer": END},
        )
        graph.add_edge("build_context", END)
        return graph.compile()

    def _build_finalize_graph(self):
        """Streaming, parte 2: validacao das citacoes, fallback e gravacao."""
        graph = StateGraph(ChatState)
        self._add_finalization(graph)
        graph.add_node("finalize_answer", _unchanged)
        graph.set_entry_point("finalize_answer")
        graph.add_conditional_edges(
            "finalize_answer",
            self._next_after_evaluation,
            {
                "build_context": "validate_citations",
                "fallback_answer": "fallback_answer",
            },
        )
        return graph.compile()

    def _add_preparation(self, graph) -> None:
        for name, node in (
            ("load_conversation_history", self._load_conversation_history),
            ("persist_user_message", self._persist_user_message),
            ("rewrite_question", self._rewrite_question),
            ("retrieve_context", self._retrieve_context),
            ("rerank_context", self._rerank_context),
            ("evaluate_context", self._evaluate_context),
            ("build_context", self._build_context),
        ):
            self._add_node(graph, name, node)
        graph.add_edge("load_conversation_history", "persist_user_message")
        graph.add_edge("persist_user_message", "rewrite_question")
        graph.add_edge("rewrite_question", "retrieve_context")
        graph.add_edge("retrieve_context", "rerank_context")
        graph.add_edge("rerank_context", "evaluate_context")

    def _add_finalization(self, graph) -> None:
        for name, node in (
            ("validate_citations", self._validate_citations),
            ("fallback_answer", self._fallback_answer),
            ("persist_assistant_message", self._persist_assistant_message),
        ):
            self._add_node(graph, name, node)
        graph.add_conditional_edges(
            "validate_citations",
            self._next_after_validation,
            {
                "persist_assistant_message": "persist_assistant_message",
                "fallback_answer": "fallback_answer",
            },
        )
        graph.add_edge("fallback_answer", "persist_assistant_message")
        graph.add_edge("persist_assistant_message", END)

    def _add_node(self, graph, name: str, node: ChatNode) -> None:
        """RF-56: cada no do grafo vira um trecho do rastreamento."""
        tracer = self._tracer

        def traced(state: ChatState) -> ChatState:
            with tracer.span(f"chat.{name}", {"graph.node": name}):
                return node(state)

        graph.add_node(name, traced)

    def _load_conversation_history(self, state: ChatState) -> ChatState:
        """RN-19: o historico ja sai limitado ao orcamento de tokens."""
        history = self._conversation_repository.list_messages(
            state["conversation_id"]
        )
        window = trim_history(
            history,
            self._token_counter,
            self._retriever.settings.history_token_budget,
        )
        logger.info(
            "chat.history.loaded",
            extra={
                "history_messages": len(history),
                "history_messages_sent": len(window),
            },
        )
        return {
            **state,
            "conversation_history": window,
        }

    def _persist_user_message(self, state: ChatState) -> ChatState:
        saved = self._conversation_repository.save_message(
            ChatMessage(
                id=MessageId(str(uuid4())),
                conversation_id=state["conversation_id"],
                role=MessageRole.USER,
                content=state["question"],
            )
        )
        return {
            **state,
            "user_message": saved,
        }

    def _rewrite_question(self, state: ChatState) -> ChatState:
        completion = self._answer_generator.rewrite(
            state["question"],
            state["conversation_history"],
        )
        search_query = completion.text
        usage = state["usage"] + completion.usage
        self._usage_so_far = usage
        logger.info(
            "chat.question.rewritten",
            extra={"rewritten": search_query != state["question"]},
        )
        return {
            **state,
            "search_query": search_query,
            "usage": usage,
        }

    def _retrieve_context(self, state: ChatState) -> ChatState:
        started_at = time.perf_counter()
        candidates = self._retriever.search(
            state["assistant_id"],
            state["search_query"],
            user_groups=state["user_groups"],
        )
        logger.info(
            "chat.retrieval.finished",
            extra={
                "candidates": len(candidates),
                "duration_ms": _elapsed_ms(started_at),
            },
        )
        return {
            **state,
            "candidates": candidates,
        }

    def _rerank_context(self, state: ChatState) -> ChatState:
        started_at = time.perf_counter()
        ranked = self._retriever.rerank(
            state["search_query"],
            state["candidates"],
            limit=state["top_n"],
        )
        self._ranked_so_far = ranked
        logger.info(
            "chat.rerank.finished",
            extra={
                "ranked": len(ranked),
                "top_score": round(ranked[0].score, 4) if ranked else None,
                "duration_ms": _elapsed_ms(started_at),
            },
        )
        return {
            **state,
            "ranked": ranked,
        }

    def _evaluate_context(self, state: ChatState) -> ChatState:
        relevant = self._retriever.select_relevant(state["ranked"])
        logger.info(
            "chat.context.evaluated",
            extra={
                "search_results": len(state["ranked"]),
                "context_chunks": len(relevant),
            },
        )
        return {
            **state,
            "relevant": relevant,
            "context_chunks": [],
            "citations": (),
            "fallback_used": not relevant,
        }

    def _next_after_evaluation(self, state: ChatState) -> str:
        if state["fallback_used"]:
            return "fallback_answer"
        return "build_context"

    def _build_context(self, state: ChatState) -> ChatState:
        context_chunks = fit_context(
            state["relevant"],
            self._token_counter,
            self._retriever.settings.context_token_budget,
        )
        return {
            **state,
            "context_chunks": context_chunks,
            "injection_flags": self._flag_injection(state, context_chunks),
        }

    def _flag_injection(
        self,
        state: ChatState,
        context_chunks: list[ContextChunk],
    ) -> int:
        """RF-60: sinaliza e registra; a resposta segue (RN-31 ja protege)."""
        flagged = [
            {
                "document_id": chunk.document_id.value if chunk.document_id else None,
                "chunk_id": chunk.chunk_id,
                "patterns": list(patterns),
            }
            for chunk in context_chunks
            if (patterns := detect_prompt_injection(chunk.text))
        ]
        if not flagged:
            return 0
        self._metrics.increment(
            "nexus_prompt_injection_suspected_total", float(len(flagged))
        )
        logger.warning(
            "chat.prompt_injection.suspected",
            extra={"flagged_chunks": len(flagged)},
        )
        self._access.audit(
            state["user"],
            AuditAction.PROMPT_INJECTION_SUSPECTED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=state["assistant_id"].value,
            details={
                "assistant_id": state["assistant_id"].value,
                "conversation_id": state["conversation_id"].value,
                "chunks": flagged,
            },
        )
        return len(flagged)

    def _generate_answer(self, state: ChatState) -> ChatState:
        logger.info(
            "chat.answer.generating",
            extra={
                "context_chunks": len(state["context_chunks"]),
                "history_messages": len(state["conversation_history"]),
            },
        )
        completion = self._answer_generator.generate_completion(
            question=state["question"],
            context_chunks=state["context_chunks"],
            history=state["conversation_history"],
            instruction=state["assistant_initial_prompt"],
        )
        usage = state["usage"] + completion.usage
        self._usage_so_far = usage
        return {
            **state,
            "answer": completion.text,
            "usage": usage,
        }

    def _validate_citations(self, state: ChatState) -> ChatState:
        grounded = self._answer_generator.validate(
            state["answer"],
            state["context_chunks"],
        )
        if grounded is None:
            logger.info(
                "chat.answer.rejected",
                extra={"reason": "no_valid_citation"},
            )
            return {
                **state,
                "fallback_used": True,
            }
        return {
            **state,
            "answer": grounded.text,
            "citations": grounded.citations,
            "fallback_used": False,
        }

    def _next_after_validation(self, state: ChatState) -> str:
        if state["fallback_used"]:
            return "fallback_answer"
        return "persist_assistant_message"

    def _fallback_answer(self, state: ChatState) -> ChatState:
        logger.info(
            "chat.fallback.used",
            extra={"context_chunks": len(state["context_chunks"])},
        )
        return {
            **state,
            "answer": state["fallback_answer"],
            "citations": (),
            "fallback_used": True,
        }

    def _persist_assistant_message(self, state: ChatState) -> ChatState:
        saved = self._conversation_repository.save_message(
            ChatMessage(
                id=MessageId(str(uuid4())),
                conversation_id=state["conversation_id"],
                role=MessageRole.ASSISTANT,
                content=state["answer"],
                citations=state["citations"],
            )
        )
        return {
            **state,
            "assistant_message": saved,
        }


def _retrieved(ranked: list[SearchResult]) -> list[dict[str, object]]:
    return [
        {
            "document_id": item.document_id.value,
            "source_name": item.source_name,
            "chunk_id": item.chunk_id,
            "score": round(item.score, 4),
        }
        for item in ranked
    ]


def _unchanged(state: ChatState) -> ChatState:
    return state


def _turn_attributes(state: ChatState, mode: str) -> dict[str, str]:
    """Identificadores apenas; nunca a pergunta (RNF-25)."""
    return {
        "chat.mode": mode,
        "nexus.conversation_id": state["conversation_id"].value,
        "nexus.assistant_id": state["assistant_id"].value,
    }


def _elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)
