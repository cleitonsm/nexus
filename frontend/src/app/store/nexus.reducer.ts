import { createReducer, on } from "@ngrx/store";

import {
  ApiKeyStatus,
  Assistant,
  ChatMessage,
  Conversation,
  IngestedDocument
} from "../shared/models/nexus.models";
import { nexusActions } from "./nexus.actions";

export const nexusFeatureKey = "nexus";

export interface NexusState {
  assistants: Assistant[];
  activeAssistantId: string | null;
  conversationHistoryByAssistant: Record<string, Conversation[]>;
  selectedConversationByAssistant: Record<string, string | null>;
  currentConversationId: string | null;
  messagesByConversation: Record<string, ChatMessage[]>;
  documents: IngestedDocument[];
  apiKeyStatus: ApiKeyStatus | null;
  loading: {
    assistants: boolean;
    createAssistant: boolean;
    createConversation: boolean;
    uploadDocument: boolean;
    sendChat: boolean;
    apiKeyStatus: boolean;
    saveApiKey: boolean;
  };
  error: string | null;
}

export const initialNexusState: NexusState = {
  assistants: [],
  activeAssistantId: null,
  conversationHistoryByAssistant: {},
  selectedConversationByAssistant: {},
  currentConversationId: null,
  messagesByConversation: {},
  documents: [],
  apiKeyStatus: null,
  loading: {
    assistants: false,
    createAssistant: false,
    createConversation: false,
    uploadDocument: false,
    sendChat: false,
    apiKeyStatus: false,
    saveApiKey: false
  },
  error: null
};

export const nexusReducer = createReducer(
  initialNexusState,
  on(nexusActions.clearError, (state) => ({ ...state, error: null })),

  on(nexusActions.loadAssistants, (state) => ({
    ...state,
    loading: { ...state.loading, assistants: true },
    error: null
  })),
  on(nexusActions.loadAssistantsSuccess, (state, { assistants }) => ({
    ...state,
    assistants,
    loading: { ...state.loading, assistants: false }
  })),
  on(nexusActions.loadAssistantsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, assistants: false },
    error
  })),

  on(nexusActions.createAssistant, (state) => ({
    ...state,
    loading: { ...state.loading, createAssistant: true },
    error: null
  })),
  on(nexusActions.createAssistantSuccess, (state, { assistant }) => ({
    ...state,
    assistants: [assistant, ...state.assistants],
    activeAssistantId: assistant.id,
    currentConversationId: null,
    loading: { ...state.loading, createAssistant: false }
  })),
  on(nexusActions.createAssistantFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, createAssistant: false },
    error
  })),

  on(nexusActions.selectAssistant, (state, { assistantId }) => {
    const selectedConversationId = state.selectedConversationByAssistant[assistantId] ?? null;
    const firstConversationId = state.conversationHistoryByAssistant[assistantId]?.[0]?.id ?? null;
    return {
      ...state,
      activeAssistantId: assistantId,
      currentConversationId: selectedConversationId ?? firstConversationId
    };
  }),

  on(nexusActions.createConversation, (state) => ({
    ...state,
    loading: { ...state.loading, createConversation: true },
    error: null
  })),
  on(nexusActions.createConversationSuccess, (state, { assistantId, conversation }) => {
    const existing = state.conversationHistoryByAssistant[assistantId] ?? [];
    return {
      ...state,
      conversationHistoryByAssistant: {
        ...state.conversationHistoryByAssistant,
        [assistantId]: [conversation, ...existing.filter((item) => item.id !== conversation.id)]
      },
      selectedConversationByAssistant: {
        ...state.selectedConversationByAssistant,
        [assistantId]: conversation.id
      },
      currentConversationId:
        state.activeAssistantId === assistantId ? conversation.id : state.currentConversationId,
      loading: { ...state.loading, createConversation: false }
    };
  }),
  on(nexusActions.createConversationFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, createConversation: false },
    error
  })),
  on(nexusActions.loadAssistantConversations, (state) => ({
    ...state,
    error: null
  })),
  on(nexusActions.loadAssistantConversationsSuccess, (state, { assistantId, conversations }) => {
    const selectedConversationId = state.selectedConversationByAssistant[assistantId] ?? null;
    const hasSelectedConversation = conversations.some(
      (conversation) => conversation.id === selectedConversationId
    );
    const fallbackConversationId = conversations[0]?.id ?? null;
    const nextConversationId = hasSelectedConversation
      ? selectedConversationId
      : fallbackConversationId;

    return {
      ...state,
      conversationHistoryByAssistant: {
        ...state.conversationHistoryByAssistant,
        [assistantId]: conversations
      },
      selectedConversationByAssistant: {
        ...state.selectedConversationByAssistant,
        [assistantId]: nextConversationId
      },
      currentConversationId:
        state.activeAssistantId === assistantId ? nextConversationId : state.currentConversationId
    };
  }),
  on(nexusActions.loadAssistantConversationsFailure, (state, { error }) => ({
    ...state,
    error
  })),
  on(nexusActions.selectConversation, (state, { conversationId }) => {
    if (!state.activeAssistantId) {
      return state;
    }
    return {
      ...state,
      currentConversationId: conversationId,
      selectedConversationByAssistant: {
        ...state.selectedConversationByAssistant,
        [state.activeAssistantId]: conversationId
      }
    };
  }),

  on(nexusActions.loadConversationSuccess, (state, { conversationId, messages }) => ({
    ...state,
    messagesByConversation: {
      ...state.messagesByConversation,
      [conversationId]: messages
    }
  })),
  on(nexusActions.loadConversationFailure, (state, { error }) => ({
    ...state,
    error
  })),

  on(nexusActions.uploadDocument, (state) => ({
    ...state,
    loading: { ...state.loading, uploadDocument: true },
    error: null
  })),
  on(nexusActions.uploadDocumentSuccess, (state, { document }) => ({
    ...state,
    documents: [document, ...state.documents],
    loading: { ...state.loading, uploadDocument: false }
  })),
  on(nexusActions.uploadDocumentFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, uploadDocument: false },
    error
  })),

  on(nexusActions.sendChatQuestion, (state) => ({
    ...state,
    loading: { ...state.loading, sendChat: true },
    error: null
  })),
  on(
    nexusActions.sendChatQuestionSuccess,
    (state, { conversationId, userMessage, assistantMessage }) => {
      const existingMessages = state.messagesByConversation[conversationId] ?? [];
      return {
        ...state,
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: [...existingMessages, userMessage, assistantMessage]
        },
        loading: { ...state.loading, sendChat: false }
      };
    }
  ),
  on(nexusActions.sendChatQuestionFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, sendChat: false },
    error
  })),

  on(nexusActions.loadApiKeyStatus, (state) => ({
    ...state,
    loading: { ...state.loading, apiKeyStatus: true },
    error: null
  })),
  on(nexusActions.loadApiKeyStatusSuccess, (state, { status }) => ({
    ...state,
    apiKeyStatus: status,
    loading: { ...state.loading, apiKeyStatus: false }
  })),
  on(nexusActions.loadApiKeyStatusFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, apiKeyStatus: false },
    error
  })),

  on(nexusActions.saveApiKey, (state) => ({
    ...state,
    loading: { ...state.loading, saveApiKey: true },
    error: null
  })),
  on(nexusActions.saveApiKeySuccess, (state, { status }) => ({
    ...state,
    apiKeyStatus: status,
    loading: { ...state.loading, saveApiKey: false }
  })),
  on(nexusActions.saveApiKeyFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, saveApiKey: false },
    error
  }))
);
