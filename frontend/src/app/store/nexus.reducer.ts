import { createReducer, on } from "@ngrx/store";

import {
  ApiKeyTestResult,
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
  apiKeyTestResult: ApiKeyTestResult | null;
  loading: {
    assistants: boolean;
    createAssistant: boolean;
    deleteAssistant: boolean;
    createConversation: boolean;
    deleteConversation: boolean;
    uploadDocument: boolean;
    sendChat: boolean;
    apiKeyStatus: boolean;
    saveApiKey: boolean;
    testApiKey: boolean;
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
  apiKeyTestResult: null,
  loading: {
    assistants: false,
    createAssistant: false,
    deleteAssistant: false,
    createConversation: false,
    deleteConversation: false,
    uploadDocument: false,
    sendChat: false,
    apiKeyStatus: false,
    saveApiKey: false,
    testApiKey: false
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
  on(nexusActions.deleteAssistant, (state) => ({
    ...state,
    loading: { ...state.loading, deleteAssistant: true },
    error: null
  })),
  on(nexusActions.deleteAssistantSuccess, (state, { assistantId }) => {
    const remainingAssistants = state.assistants.filter((assistant) => assistant.id !== assistantId);
    const {
      [assistantId]: _removedConversations,
      ...conversationHistoryByAssistant
    } = state.conversationHistoryByAssistant;
    const {
      [assistantId]: _removedSelectedConversation,
      ...selectedConversationByAssistant
    } = state.selectedConversationByAssistant;
    const removedConversationIds = new Set(
      state.conversationHistoryByAssistant[assistantId]?.map((conversation) => conversation.id) ?? []
    );
    const messagesByConversation = Object.fromEntries(
      Object.entries(state.messagesByConversation).filter(
        ([conversationId]) => !removedConversationIds.has(conversationId)
      )
    );
    const nextActiveAssistantId =
      state.activeAssistantId === assistantId
        ? remainingAssistants[0]?.id ?? null
        : state.activeAssistantId;
    const nextConversationId = nextActiveAssistantId
      ? selectedConversationByAssistant[nextActiveAssistantId] ??
        conversationHistoryByAssistant[nextActiveAssistantId]?.[0]?.id ??
        null
      : null;

    return {
      ...state,
      assistants: remainingAssistants,
      activeAssistantId: nextActiveAssistantId,
      conversationHistoryByAssistant,
      selectedConversationByAssistant,
      currentConversationId: nextConversationId,
      messagesByConversation,
      documents: state.documents.filter((document) => document.assistant_id !== assistantId),
      loading: { ...state.loading, deleteAssistant: false }
    };
  }),
  on(nexusActions.deleteAssistantFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, deleteAssistant: false },
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
  on(nexusActions.deleteConversation, (state) => ({
    ...state,
    loading: { ...state.loading, deleteConversation: true },
    error: null
  })),
  on(nexusActions.deleteConversationSuccess, (state, { assistantId, conversationId }) => {
    const remainingConversations = (state.conversationHistoryByAssistant[assistantId] ?? []).filter(
      (conversation) => conversation.id !== conversationId
    );
    const nextConversationId =
      state.currentConversationId === conversationId
        ? remainingConversations[0]?.id ?? null
        : state.currentConversationId;
    const {
      [conversationId]: _removedMessages,
      ...messagesByConversation
    } = state.messagesByConversation;

    return {
      ...state,
      conversationHistoryByAssistant: {
        ...state.conversationHistoryByAssistant,
        [assistantId]: remainingConversations
      },
      selectedConversationByAssistant: {
        ...state.selectedConversationByAssistant,
        [assistantId]:
          state.selectedConversationByAssistant[assistantId] === conversationId
            ? remainingConversations[0]?.id ?? null
            : state.selectedConversationByAssistant[assistantId] ?? null
      },
      currentConversationId: nextConversationId,
      messagesByConversation,
      loading: { ...state.loading, deleteConversation: false }
    };
  }),
  on(nexusActions.deleteConversationFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, deleteConversation: false },
    error
  })),

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
    apiKeyTestResult: null,
    loading: { ...state.loading, saveApiKey: false }
  })),
  on(nexusActions.saveApiKeyFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, saveApiKey: false },
    error
  })),
  on(nexusActions.testApiKey, (state) => ({
    ...state,
    apiKeyTestResult: null,
    loading: { ...state.loading, testApiKey: true },
    error: null
  })),
  on(nexusActions.testApiKeySuccess, (state, { result }) => ({
    ...state,
    apiKeyTestResult: result,
    loading: { ...state.loading, testApiKey: false }
  })),
  on(nexusActions.testApiKeyFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, testApiKey: false },
    error
  }))
);
