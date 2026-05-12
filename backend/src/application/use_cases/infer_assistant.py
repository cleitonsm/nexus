from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TypedDict

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from src.domain import LLMGateway


@dataclass(frozen=True, slots=True)
class InferAssistantInput:
    question: str
    assistants: list[dict[str, str | None]]


@dataclass(frozen=True, slots=True)
class InferAssistantOutput:
    assistant_id: str | None


class InferAssistantState(TypedDict):
    question: str
    assistants: list[dict[str, str | None]]
    prompt: str
    raw_response: str
    assistant_id: str | None


class InferAssistantUseCase:
    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm_gateway = llm_gateway
        self._graph = self._build_graph()

    def execute(self, data: InferAssistantInput) -> InferAssistantOutput:
        question = data.question.strip()
        if not question:
            raise ValueError("question must not be empty.")
        if not data.assistants:
            return InferAssistantOutput(assistant_id=None)

        final_state = self._graph.invoke(
            {
                "question": question,
                "assistants": data.assistants,
            }
        )
        return InferAssistantOutput(assistant_id=final_state["assistant_id"])

    def _build_graph(self):
        graph = StateGraph(InferAssistantState)
        graph.add_node("build_prompt", self._build_prompt)
        graph.add_node("call_llm", self._call_llm)
        graph.add_node("parse_response", self._parse_response)
        graph.add_node("validate_id", self._validate_id)
        graph.set_entry_point("build_prompt")
        graph.add_edge("build_prompt", "call_llm")
        graph.add_edge("call_llm", "parse_response")
        graph.add_edge("parse_response", "validate_id")
        graph.add_edge("validate_id", END)
        return graph.compile()

    def _build_prompt(self, state: InferAssistantState) -> InferAssistantState:
        assistants_catalog = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "initial_prompt": item.get("initial_prompt"),
            }
            for item in state["assistants"]
        ]
        assistants_json = json.dumps(assistants_catalog, ensure_ascii=True)
        prompt = (
            "Escolha o assistente mais adequado para responder a "
            "pergunta do usuario.\n"
            "Responda estritamente em JSON valido no formato:\n"
            '{"assistant_id": "<id>"}\n'
            "Se nenhum assistente for adequado, responda "
            '{"assistant_id": null}.\n\n'
            f"Pergunta:\n{state['question']}\n\n"
            f"Assistentes:\n{assistants_json}"
        )
        return {**state, "prompt": prompt}

    def _call_llm(self, state: InferAssistantState) -> InferAssistantState:
        raw_response = self._llm_gateway.generate(
            prompt=state["prompt"],
            context_chunks=[],
            conversation_history=[],
        )
        return {**state, "raw_response": raw_response}

    def _parse_response(
        self, state: InferAssistantState
    ) -> InferAssistantState:
        assistant_id: str | None = None
        try:
            payload = json.loads(state["raw_response"])
            value = payload.get("assistant_id")
            if isinstance(value, str) and value.strip():
                assistant_id = value.strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            assistant_id = None
        return {**state, "assistant_id": assistant_id}

    def _validate_id(self, state: InferAssistantState) -> InferAssistantState:
        assistant_id = state["assistant_id"]
        valid_ids = {
            str(item.get("id")).strip()
            for item in state["assistants"]
            if item.get("id")
        }
        if assistant_id not in valid_ids:
            return {**state, "assistant_id": None}
        return state
