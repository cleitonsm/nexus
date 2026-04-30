from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from src.application.dto import ChatTurnResult, MessageDTO
from src.domain import (
    AssistantId,
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
        conversation_repository: ConversationRepository,
        embedding_gateway: EmbeddingGateway,
        vector_store_gateway: VectorStoreGateway,
        llm_gateway: LLMGateway,
    ) -> None:
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

        final_state = self._graph.invoke(
            {
                "conversation_id": conversation_id,
                "assistant_id": conversation.assistant_id,
                "question": question,
                "top_k": max(data.top_k, 1),
                "fallback_answer": data.fallback_answer,
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
        graph.add_node("load_conversation_history", self._load_conversation_history)
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
        history = self._conversation_repository.list_messages(state["conversation_id"])
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
        return {
            **state,
            "fallback_used": len(state["context_chunks"]) == 0,
        }

    def _next_after_evaluation(self, state: ChatState) -> str:
        if state["fallback_used"]:
            return "fallback_answer"
        return "generate_answer"

    def _generate_answer(self, state: ChatState) -> ChatState:
        prompt = (
            "Responda de forma objetiva usando apenas o contexto recuperado.\n"
            f"Pergunta: {state['question']}"
        )
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
