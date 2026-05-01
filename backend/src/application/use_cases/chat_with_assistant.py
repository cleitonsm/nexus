from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from src.application.dto import ChatTurnResult, MessageDTO
from src.domain import (
    AssistantId,
    AssistantRepository,
    ChatMessage,
    CollectionName,
    ConversationId,
    ConversationRepository,
    EmbeddingGateway,
    LLMGateway,
    MessageId,
    MessageRole,
    SearchResult,
    VectorStoreGateway,
)


class ConversationNotFoundError(ValueError):
    pass


def _agent_debug_log(
    *,
    run_id: str,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, object],
) -> None:
    payload = {
        "sessionId": "a1f259",
        "id": f"log_{int(time.time() * 1000)}_{uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    try:
        with Path("debug-a1f259.log").open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
        pass


@dataclass(frozen=True, slots=True)
class ChatWithAssistantInput:
    conversation_id: str
    question: str
    top_k: int = 4
    fallback_answer: str = (
        "Nao encontrei contexto suficiente nos documentos deste assistente "
        "para responder com seguranca."
    )


class ChatState(TypedDict):
    conversation_id: ConversationId
    assistant_id: AssistantId
    question: str
    top_k: int
    fallback_answer: str
    assistant_initial_prompt: str | None
    conversation_history: list[ChatMessage]
    user_message: ChatMessage
    search_results: list[SearchResult]
    context_chunks: list[str]
    fallback_used: bool
    answer: str
    assistant_message: ChatMessage


class ChatWithAssistantUseCase:
    def __init__(
        self,
        *,
        assistant_repository: AssistantRepository,
        conversation_repository: ConversationRepository,
        embedding_gateway: EmbeddingGateway,
        vector_store_gateway: VectorStoreGateway,
        llm_gateway: LLMGateway,
    ) -> None:
        self._assistant_repository = assistant_repository
        self._conversation_repository = conversation_repository
        self._embedding_gateway = embedding_gateway
        self._vector_store_gateway = vector_store_gateway
        self._llm_gateway = llm_gateway
        self._graph = self._build_graph()

    def execute(self, data: ChatWithAssistantInput) -> ChatTurnResult:
        question = data.question.strip()
        if not question:
            raise ValueError("question must not be empty.")

        conversation_id = ConversationId(data.conversation_id)
        conversation = self._conversation_repository.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError("conversation not found.")
        assistant = self._assistant_repository.get_by_id(
            conversation.assistant_id
        )

        final_state = self._graph.invoke(
            {
                "conversation_id": conversation_id,
                "assistant_id": conversation.assistant_id,
                "question": question,
                "top_k": max(data.top_k, 1),
                "fallback_answer": data.fallback_answer,
                "assistant_initial_prompt": (
                    assistant.initial_prompt if assistant else None
                ),
            }
        )
        return ChatTurnResult(
            conversation_id=final_state["conversation_id"].value,
            assistant_id=final_state["assistant_id"].value,
            user_message=MessageDTO.from_entity(final_state["user_message"]),
            assistant_message=MessageDTO.from_entity(
                final_state["assistant_message"]
            ),
            used_context_chunks=len(final_state["context_chunks"]),
            fallback_used=final_state["fallback_used"],
        )

    def _build_graph(self):
        graph = StateGraph(ChatState)
        graph.add_node(
            "load_conversation_history",
            self._load_conversation_history,
        )
        graph.add_node("persist_user_message", self._persist_user_message)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("evaluate_context", self._evaluate_context)
        graph.add_node("generate_answer", self._generate_answer)
        graph.add_node("fallback_answer", self._fallback_answer)
        graph.add_node(
            "persist_assistant_message",
            self._persist_assistant_message,
        )

        graph.set_entry_point("load_conversation_history")
        graph.add_edge("load_conversation_history", "persist_user_message")
        graph.add_edge("persist_user_message", "retrieve_context")
        graph.add_edge("retrieve_context", "evaluate_context")
        graph.add_conditional_edges(
            "evaluate_context",
            self._next_after_evaluation,
            {
                "generate_answer": "generate_answer",
                "fallback_answer": "fallback_answer",
            },
        )
        graph.add_edge("generate_answer", "persist_assistant_message")
        graph.add_edge("fallback_answer", "persist_assistant_message")
        graph.add_edge("persist_assistant_message", END)
        return graph.compile()

    def _load_conversation_history(self, state: ChatState) -> ChatState:
        history = self._conversation_repository.list_messages(
            state["conversation_id"]
        )
        return {
            **state,
            "conversation_history": history,
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

    def _retrieve_context(self, state: ChatState) -> ChatState:
        query_vector = self._embedding_gateway.embed_texts([state["question"]])
        if not query_vector:
            return {
                **state,
                "search_results": [],
                "context_chunks": [],
            }

        collection_name = CollectionName.from_assistant_id(
            state["assistant_id"]
        )
        search_results = self._vector_store_gateway.search(
            collection_name=collection_name,
            query_vector=query_vector[0],
            limit=state["top_k"],
        )
        return {
            **state,
            "search_results": search_results,
            "context_chunks": [
                item.text for item in search_results if item.text.strip()
            ],
        }

    def _evaluate_context(self, state: ChatState) -> ChatState:
        # region agent log
        _agent_debug_log(
            run_id="llm-ui-pre-fix",
            hypothesis_id="H8",
            location="backend/src/application/use_cases/chat_with_assistant.py:evaluate_context",
            message="evaluating retrieved chat context",
            data={
                "searchResults": len(state["search_results"]),
                "contextChunks": len(state["context_chunks"]),
            },
        )
        # endregion
        return {
            **state,
            "fallback_used": len(state["context_chunks"]) == 0,
        }

    def _next_after_evaluation(self, state: ChatState) -> str:
        if state["fallback_used"]:
            return "fallback_answer"
        return "generate_answer"

    def _generate_answer(self, state: ChatState) -> ChatState:
        instruction = (
            state["assistant_initial_prompt"].strip()
            if state["assistant_initial_prompt"]
            else (
                "Responda de forma objetiva usando apenas o contexto "
                "recuperado."
            )
        )
        prompt = (
            f"{instruction}\n"
            f"Pergunta: {state['question']}"
        )
        # region agent log
        _agent_debug_log(
            run_id="llm-ui-pre-fix",
            hypothesis_id="H7,H9",
            location="backend/src/application/use_cases/chat_with_assistant.py:generate_answer",
            message="calling llm gateway",
            data={
                "contextChunks": len(state["context_chunks"]),
                "historyMessages": len(state["conversation_history"]),
                "promptLength": len(prompt),
            },
        )
        # endregion
        answer = self._llm_gateway.generate(
            prompt=prompt,
            context_chunks=state["context_chunks"],
            conversation_history=state["conversation_history"],
        ).strip()
        if not answer:
            answer = state["fallback_answer"]
            fallback_used = True
        else:
            fallback_used = False
        return {
            **state,
            "answer": answer,
            "fallback_used": fallback_used,
        }

    def _fallback_answer(self, state: ChatState) -> ChatState:
        # region agent log
        _agent_debug_log(
            run_id="llm-ui-pre-fix",
            hypothesis_id="H8",
            location="backend/src/application/use_cases/chat_with_assistant.py:fallback_answer",
            message="using fallback answer without llm call",
            data={"contextChunks": len(state["context_chunks"])},
        )
        # endregion
        return {
            **state,
            "answer": state["fallback_answer"],
            "fallback_used": True,
        }

    def _persist_assistant_message(self, state: ChatState) -> ChatState:
        saved = self._conversation_repository.save_message(
            ChatMessage(
                id=MessageId(str(uuid4())),
                conversation_id=state["conversation_id"],
                role=MessageRole.ASSISTANT,
                content=state["answer"],
            )
        )
        return {
            **state,
            "assistant_message": saved,
        }
