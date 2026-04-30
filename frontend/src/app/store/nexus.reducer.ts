import { createReducer, on } from "@ngrx/store";

import { ChatMessage, IngestedDocument, Assistant } from "../shared/models/nexus.models";
import { nexusActions } from "./nexus.actions";

export const nexusFeatureKey = "nexus";

export interface NexusState {
  assistants: Assistant[];
  activeAssistantId: string | null;
  conversationsByAssistant: Record<string, string>;
  currentConversationId: string | null;
  messagesByConversation: Record<string, ChatMessage[]>;
  documents: IngestedDocument[];
  loading: {
    assistants: boolean;
    createAssistant: boolean;
    createConversation: boolean;
    uploadDocument: boolean;
    sendChat: boolean;
  };
  error: string | null;
}

export const initialNexusState: NexusState = {
  assistants: [],
  activeAssistantId: null,
  conversationsByAssistant: {},
  currentConversationId: null,
  messagesByConversation: {},
  documents: [],
  loading: {
    assistants: false,
    createAssistant: false,
    createConversation: false,
    uploadDocument: false,
    sendChat: false
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
    loading: { ...state.loading, createAssistant: false }
  })),
  on(nexusActions.createAssistantFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, createAssistant: false },
    error
  })),

  on(nexusActions.selectAssistant, (state, { assistantId }) => {
    const mappedConversationId = state.conversationsByAssistant[assistantId] ?? null;
    return {
      ...state,
      activeAssistantId: assistantId,
      currentConversationId: mappedConversationId
    };
  }),

  on(nexusActions.createConversation, (state) => ({
    ...state,
    loading: { ...state.loading, createConversation: true },
    error: null
  })),
  on(nexusActions.createConversationSuccess, (state, { assistantId, conversationId }) => ({
    ...state,
    conversationsByAssistant: {
      ...state.conversationsByAssistant,
      [assistantId]: conversationId
    },
    currentConversationId:
      state.activeAssistantId === assistantId ? conversationId : state.currentConversationId,
    loading: { ...state.loading, createConversation: false }
  })),
  on(nexusActions.createConversationFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, createConversation: false },
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
  }))
);
