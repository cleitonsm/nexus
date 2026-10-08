import "@angular/compiler";
import { describe, expect, it } from "vitest";

import {
  Assistant,
  ChatMessage,
  Citation,
  Conversation,
  DocumentAccess
} from "../shared/models/nexus.models";
import { nexusActions } from "./nexus.actions";
import {
  initialNexusState,
  NexusState,
  nexusReducer
} from "./nexus.reducer";
import {
  selectActiveAssistantConversations,
  selectActiveDocumentAccess,
  selectAuditEvents,
  selectCurrentCitationsByMessage,
  selectCurrentMessages
} from "./nexus.selectors";

const assistantConversation = (
  id: string,
  assistantId = "assistant-1"
): Conversation => ({
  id,
  assistant_id: assistantId,
  name: null,
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

const citation = (number: number, sourceName = "politica.pdf"): Citation => ({
  number,
  document_id: "doc-1",
  chunk_id: `doc-1:${number}`,
  source_name: sourceName,
  section_path: "Ferias > Duracao",
  page: 3,
  score: 0.9,
  excerpt: `Trecho ${number}.`
});

const assistant = (id: string): Assistant => ({
  id,
  name: `Assistant ${id}`,
  description: null,
  initial_prompt: null,
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

  it("removes assistant related state when deleting assistant", () => {
    const state: NexusState = {
      ...initialNexusState,
      assistants: [assistant("assistant-1"), assistant("assistant-2")],
      activeAssistantId: "assistant-1",
      currentConversationId: "conv-1",
      conversationHistoryByAssistant: {
        "assistant-1": [assistantConversation("conv-1")]
      },
      selectedConversationByAssistant: {
        "assistant-1": "conv-1"
      },
      messagesByConversation: {
        "conv-1": [chatMessage("msg-1", "user")]
      },
      loading: { ...initialNexusState.loading, deleteAssistant: true }
    };

    const nextState = nexusReducer(
      state,
      nexusActions.deleteAssistantSuccess({ assistantId: "assistant-1" })
    );

    expect(nextState.assistants).toHaveLength(1);
    expect(nextState.activeAssistantId).toBe("assistant-2");
    expect(nextState.currentConversationId).toBeNull();
    expect(nextState.messagesByConversation["conv-1"]).toBeUndefined();
    expect(nextState.loading.deleteAssistant).toBe(false);
  });

  it("removes deleted conversation from active assistant history", () => {
    const state: NexusState = {
      ...initialNexusState,
      activeAssistantId: "assistant-1",
      currentConversationId: "conv-1",
      conversationHistoryByAssistant: {
        "assistant-1": [assistantConversation("conv-1"), assistantConversation("conv-2")]
      },
      selectedConversationByAssistant: {
        "assistant-1": "conv-1"
      },
      messagesByConversation: {
        "conv-1": [chatMessage("msg-1", "user")]
      },
      loading: { ...initialNexusState.loading, deleteConversation: true }
    };

    const nextState = nexusReducer(
      state,
      nexusActions.deleteConversationSuccess({
        assistantId: "assistant-1",
        conversationId: "conv-1"
      })
    );

    expect(nextState.conversationHistoryByAssistant["assistant-1"]).toHaveLength(1);
    expect(nextState.currentConversationId).toBe("conv-2");
    expect(nextState.messagesByConversation["conv-1"]).toBeUndefined();
    expect(nextState.loading.deleteConversation).toBe(false);
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

// CT-21 (SPEC-20261007-003): o reducer armazena as fontes e o seletor as expoe.
describe("citations", () => {
  const answered: ChatMessage = {
    ...chatMessage("msg-2", "assistant"),
    citations: [citation(2), citation(1)]
  };

  it("stores the sources returned with a chat answer", () => {
    const nextState = nexusReducer(
      { ...initialNexusState, currentConversationId: "conv-1" },
      nexusActions.sendChatQuestionSuccess({
        conversationId: "conv-1",
        userMessage: chatMessage("msg-1", "user"),
        assistantMessage: answered
      })
    );

    const [, stored] = nextState.messagesByConversation["conv-1"];
    expect(stored.citations).toHaveLength(2);
    expect(stored.citations?.[0].source_name).toBe("politica.pdf");
  });

  it("stores the sources of a loaded conversation", () => {
    const nextState = nexusReducer(
      initialNexusState,
      nexusActions.loadConversationSuccess({
        conversationId: "conv-1",
        messages: [chatMessage("msg-1", "user"), answered]
      })
    );

    expect(nextState.messagesByConversation["conv-1"][1].citations).toHaveLength(2);
  });

  it("exposes the sources by message, ordered by number", () => {
    const state = {
      nexus: {
        ...initialNexusState,
        currentConversationId: "conv-1",
        messagesByConversation: {
          "conv-1": [chatMessage("msg-1", "user"), answered],
          "conv-2": [{ ...answered, id: "msg-9" }]
        }
      }
    };

    const byMessage = selectCurrentCitationsByMessage(state);

    expect(Object.keys(byMessage)).toEqual(["msg-2"]);
    expect(byMessage["msg-2"].map((item) => item.number)).toEqual([1, 2]);
  });

  it("exposes nothing for answers without sources", () => {
    const state = {
      nexus: {
        ...initialNexusState,
        currentConversationId: "conv-1",
        messagesByConversation: {
          "conv-1": [
            chatMessage("msg-1", "user"),
            { ...chatMessage("msg-2", "assistant"), citations: [] },
            chatMessage("msg-3", "assistant")
          ]
        }
      }
    };

    expect(selectCurrentCitationsByMessage(state)).toEqual({});
  });
});

describe("access management (SPEC-004)", () => {
  const documentAccess = (id: string, groups: string[] = []): DocumentAccess => ({
    id,
    assistant_id: "assistant-1",
    source_name: `${id}.md`,
    created_at: "2026-10-07T10:00:00Z",
    chunk_count: 3,
    groups
  });

  it("stores the groups returned for an assistant", () => {
    const state = nexusReducer(
      {
        ...initialNexusState,
        assistants: [assistant("assistant-1"), assistant("assistant-2")],
        loading: { ...initialNexusState.loading, assistantGroups: true }
      },
      nexusActions.setAssistantGroupsSuccess({
        assistantId: "assistant-1",
        groups: ["financeiro", "rh"]
      })
    );

    expect(state.assistants[0]?.groups).toEqual(["financeiro", "rh"]);
    expect(state.assistants[1]?.groups).toBeUndefined();
    expect(state.loading.assistantGroups).toBe(false);
  });

  it("keeps the documents of each assistant and exposes the active one", () => {
    const loaded = nexusReducer(
      { ...initialNexusState, activeAssistantId: "assistant-1" },
      nexusActions.loadDocumentAccessSuccess({
        assistantId: "assistant-1",
        documents: [documentAccess("doc-1"), documentAccess("doc-2", ["diretoria"])]
      })
    );

    expect(selectActiveDocumentAccess({ nexus: loaded }).map((item) => item.id)).toEqual([
      "doc-1",
      "doc-2"
    ]);
    expect(
      selectActiveDocumentAccess({ nexus: { ...loaded, activeAssistantId: "assistant-2" } })
    ).toEqual([]);
    expect(selectActiveDocumentAccess({ nexus: { ...loaded, activeAssistantId: null } })).toEqual(
      []
    );
  });

  it("replaces only the document whose restriction changed", () => {
    const loaded = nexusReducer(
      initialNexusState,
      nexusActions.loadDocumentAccessSuccess({
        assistantId: "assistant-1",
        documents: [documentAccess("doc-1"), documentAccess("doc-2")]
      })
    );
    const restricted = nexusReducer(
      { ...loaded, loading: { ...loaded.loading, documentGroups: true } },
      nexusActions.setDocumentGroupsSuccess({ document: documentAccess("doc-2", ["diretoria"]) })
    );

    expect(restricted.documentAccessByAssistant["assistant-1"]).toEqual([
      documentAccess("doc-1"),
      documentAccess("doc-2", ["diretoria"])
    ]);
    expect(restricted.loading.documentGroups).toBe(false);
  });

  it("surfaces a refused change as an error and stops loading", () => {
    const state = nexusReducer(
      { ...initialNexusState, loading: { ...initialNexusState.loading, documentGroups: true } },
      nexusActions.setDocumentGroupsFailure({ error: "Você não tem permissão para esta operação." })
    );

    expect(state.error).toBe("Você não tem permissão para esta operação.");
    expect(state.loading.documentGroups).toBe(false);
  });

  it("replaces the audit events on each consultation", () => {
    const event = {
      id: "e1",
      occurred_at: "2026-10-07T12:00:00Z",
      user_id: "ana",
      action: "chat.question",
      resource_type: "assistant",
      resource_id: "assistant-1",
      details: { retrieved_documents: [{ source_name: "politica.md" }] }
    };
    const loading = nexusReducer(
      initialNexusState,
      nexusActions.loadAuditEvents({
        filters: { userId: "", action: "", assistantId: "", from: "", to: "" }
      })
    );
    const loaded = nexusReducer(loading, nexusActions.loadAuditEventsSuccess({ events: [event] }));

    expect(loading.loading.auditEvents).toBe(true);
    expect(selectAuditEvents({ nexus: loaded })).toEqual([event]);
    expect(loaded.loading.auditEvents).toBe(false);
  });
});
