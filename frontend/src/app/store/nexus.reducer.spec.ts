import "@angular/compiler";
import { describe, expect, it } from "vitest";

import { Assistant, ChatMessage, Conversation } from "../shared/models/nexus.models";
import { nexusActions } from "./nexus.actions";
import {
  initialNexusState,
  NexusState,
  nexusReducer
} from "./nexus.reducer";
import {
  selectActiveAssistantConversations,
  selectCurrentMessages
} from "./nexus.selectors";

const assistantConversation = (
  id: string,
  assistantId = "assistant-1"
): Conversation => ({
  id,
  assistant_id: assistantId,
  created_at: "2026-04-30T10:00:00Z",
  updated_at: "2026-04-30T10:00:00Z",
  message_count: 0
});

const chatMessage = (id: string, role: "user" | "assistant"): ChatMessage => ({
  id,
  conversation_id: "conv-1",
  role,
  content: `${role}-${id}`,
  created_at: "2026-04-30T10:00:00Z"
});

const assistant = (id: string): Assistant => ({
  id,
  name: `Assistant ${id}`,
  description: null,
  created_at: "2026-04-30T10:00:00Z"
});

describe("nexusReducer", () => {
  it("stores assistant conversation history and selects fallback conversation", () => {
    const stateWithAssistant = nexusReducer(
      initialNexusState,
      nexusActions.selectAssistant({ assistantId: "assistant-1" })
    );
    const nextState = nexusReducer(
      stateWithAssistant,
      nexusActions.loadAssistantConversationsSuccess({
        assistantId: "assistant-1",
        conversations: [assistantConversation("conv-1"), assistantConversation("conv-2")]
      })
    );

    expect(nextState.conversationHistoryByAssistant["assistant-1"]).toHaveLength(2);
    expect(nextState.selectedConversationByAssistant["assistant-1"]).toBe("conv-1");
    expect(nextState.currentConversationId).toBe("conv-1");
  });

  it("appends user and assistant messages on chat success", () => {
    const state: NexusState = {
      ...initialNexusState,
      currentConversationId: "conv-1",
      messagesByConversation: {
        "conv-1": [chatMessage("msg-1", "user")]
      }
    };
    const nextState = nexusReducer(
      state,
      nexusActions.sendChatQuestionSuccess({
        conversationId: "conv-1",
        userMessage: chatMessage("msg-2", "user"),
        assistantMessage: chatMessage("msg-3", "assistant")
      })
    );

    expect(nextState.messagesByConversation["conv-1"]).toHaveLength(3);
    expect(nextState.loading.sendChat).toBe(false);
  });

  it("selects a newly created assistant", () => {
    const nextState = nexusReducer(
      initialNexusState,
      nexusActions.createAssistantSuccess({ assistant: assistant("assistant-1") })
    );

    expect(nextState.assistants[0]?.id).toBe("assistant-1");
    expect(nextState.activeAssistantId).toBe("assistant-1");
    expect(nextState.currentConversationId).toBeNull();
    expect(nextState.loading.createAssistant).toBe(false);
  });

  it("stores API key status after loading or saving", () => {
    const loadedState = nexusReducer(
      {
        ...initialNexusState,
        loading: { ...initialNexusState.loading, apiKeyStatus: true }
      },
      nexusActions.loadApiKeyStatusSuccess({ status: { configured: false } })
    );
    const savedState = nexusReducer(
      {
        ...loadedState,
        loading: { ...loadedState.loading, saveApiKey: true }
      },
      nexusActions.saveApiKeySuccess({ status: { configured: true } })
    );

    expect(loadedState.apiKeyStatus?.configured).toBe(false);
    expect(loadedState.loading.apiKeyStatus).toBe(false);
    expect(savedState.apiKeyStatus?.configured).toBe(true);
    expect(savedState.loading.saveApiKey).toBe(false);
  });
});

describe("nexusSelectors", () => {
  it("returns current conversation messages", () => {
    const state = {
      nexus: {
        ...initialNexusState,
        currentConversationId: "conv-1",
        messagesByConversation: {
          "conv-1": [chatMessage("msg-1", "user"), chatMessage("msg-2", "assistant")]
        }
      }
    };

    expect(selectCurrentMessages(state)).toHaveLength(2);
  });

  it("returns active assistant conversation list", () => {
    const state = {
      nexus: {
        ...initialNexusState,
        activeAssistantId: "assistant-1",
        conversationHistoryByAssistant: {
          "assistant-1": [assistantConversation("conv-1"), assistantConversation("conv-2")]
        }
      }
    };

    expect(selectActiveAssistantConversations(state)).toHaveLength(2);
  });
});
