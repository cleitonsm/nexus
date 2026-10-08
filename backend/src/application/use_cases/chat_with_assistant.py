from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from src.application.dto import ChatTurnResult, MessageDTO
from src.application.services import (
    DEFAULT_ANSWER_INSTRUCTION,
    AccessControl,
    ContextRetriever,
    GroundedAnswerGenerator,
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
    SearchResult,
    TokenCounter,
)

__all__ = [
    "DEFAULT_ANSWER_INSTRUCTION",
    "ChatWithAssistantInput",
    "ChatWithAssistantUseCase",
    "ConversationNotFoundError",
]


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
    ) -> None:
        self._access = access_control
        self._assistant_repository = assistant_repository
        self._conversation_repository = conversation_repository
        self._retriever = context_retriever
        self._answer_generator = answer_generator
        self._token_counter = token_counter
        self._ranked_so_far: list[SearchResult] = []
        self._graph = self._build_graph()

    def execute(self, data: ChatWithAssistantInput) -> ChatTurnResult:
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
        assistant = self._assistant_repository.get_by_id(
            conversation.assistant_id
        )

        # Trechos ja ranqueados: se a pergunta falhar depois, a auditoria
        # ainda registra o que foi recuperado (C9).
        self._ranked_so_far = []
        initial_state = self._initial_state(
            data, conversation_id, conversation.assistant_id, question, assistant
        )
        try:
            final_state = self._graph.invoke(initial_state)
        except Exception as exc:
            self._audit_failure(
                data.user, conversation_id, conversation.assistant_id, exc
            )
            raise
        fallback_used = final_state["fallback_used"]
        self._audit_question(data.user, final_state)
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

    def _initial_state(
        self,
        data: ChatWithAssistantInput,
        conversation_id: ConversationId,
        assistant_id: AssistantId,
        question: str,
        assistant: Assistant | None,
    ) -> dict[str, object]:
        return {
            "conversation_id": conversation_id,
            "assistant_id": assistant_id,
            "question": question,
            "user_groups": data.user.groups,
            "top_n": self._top_n(data.top_k),
            "fallback_answer": data.fallback_answer,
            "assistant_initial_prompt": (
                assistant.initial_prompt if assistant else None
            ),
        }

    def _audit_failure(
        self,
        user: AuthenticatedUser,
        conversation_id: ConversationId,
        assistant_id: AssistantId,
        error: Exception,
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
                "error_type": type(error).__name__,
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
        graph = StateGraph(ChatState)
        graph.add_node(
            "load_conversation_history",
            self._load_conversation_history,
        )
        graph.add_node("persist_user_message", self._persist_user_message)
        graph.add_node("rewrite_question", self._rewrite_question)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("rerank_context", self._rerank_context)
        graph.add_node("evaluate_context", self._evaluate_context)
        graph.add_node("build_context", self._build_context)
        graph.add_node("generate_answer", self._generate_answer)
        graph.add_node("validate_citations", self._validate_citations)
        graph.add_node("fallback_answer", self._fallback_answer)
        graph.add_node(
            "persist_assistant_message",
            self._persist_assistant_message,
        )

        graph.set_entry_point("load_conversation_history")
        graph.add_edge("load_conversation_history", "persist_user_message")
        graph.add_edge("persist_user_message", "rewrite_question")
        graph.add_edge("rewrite_question", "retrieve_context")
        graph.add_edge("retrieve_context", "rerank_context")
        graph.add_edge("rerank_context", "evaluate_context")
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
        return graph.compile()

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
        search_query = self._answer_generator.rewrite_question(
            state["question"],
            state["conversation_history"],
        )
        logger.info(
            "chat.question.rewritten",
            extra={"rewritten": search_query != state["question"]},
        )
        return {
            **state,
            "search_query": search_query,
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
        return {
            **state,
            "context_chunks": fit_context(
                state["relevant"],
                self._token_counter,
                self._retriever.settings.context_token_budget,
            ),
        }

    def _generate_answer(self, state: ChatState) -> ChatState:
        logger.info(
            "chat.answer.generating",
            extra={
                "context_chunks": len(state["context_chunks"]),
                "history_messages": len(state["conversation_history"]),
            },
        )
        answer = self._answer_generator.generate(
            question=state["question"],
            context_chunks=state["context_chunks"],
            history=state["conversation_history"],
            instruction=state["assistant_initial_prompt"],
        )
        return {
            **state,
            "answer": answer,
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


def _elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)
