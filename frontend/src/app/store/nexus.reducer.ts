import { createReducer, on } from "@ngrx/store";

import {
  ApiKeyTestResult,
  ApiKeyStatus,
  Assistant,
  AuditEvent,
  ChatMessage,
  ChatStreamState,
  Conversation,
  ConversationDetail,
  DocumentAccess,
  FeedbackRating,
  IndexStatus,
  MessageFeedback,
  UsageLimits,
  UsageReport
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
  documents: DocumentAccess[];
  /** Documentos de cada assistente com a restricao por grupo (RF-43). */
  documentAccessByAssistant: Record<string, DocumentAccess[]>;
  /** Estado do indice de busca por assistente (RF-31, PC-D2). */
  indexStatusByAssistant: Record<string, IndexStatus>;
  /** Grupos do Keycloak (PC-D6); ``null`` quando a lista nao esta disponivel. */
  availableGroups: string[] | null;
  /** Conversas anteriores a autenticacao e a aberta para leitura (PC-D5). */
  archivedConversations: Conversation[];
  archivedConversationDetail: ConversationDetail | null;
  auditEvents: AuditEvent[];
  createAssistantModalOpen: boolean;
  inferAssistantError: string | null;
  apiKeyStatus: ApiKeyStatus | null;
  apiKeyTestResult: ApiKeyTestResult | null;
  /** Resposta em streaming em andamento (RF-58). */
  chatStream: ChatStreamState | null;
  /** Avaliacao enviada nesta sessao, por mensagem (RF-61). */
  feedbackByMessage: Record<string, MessageFeedbackState>;
  /** Avaliacoes negativas para o curador (RN-33). */
  curatorFeedback: MessageFeedback[];
  usageReport: UsageReport | null;
  usageLimits: UsageLimits | null;
  /** Aviso de sucesso das telas administrativas (ex.: limites gravados). */
  notice: string | null;
  loading: {
    assistants: boolean;
    createAssistant: boolean;
    deleteAssistant: boolean;
    createConversation: boolean;
    deleteConversation: boolean;
    uploadDocument: boolean;
    sendChat: boolean;
    inferAssistant: boolean;
    apiKeyStatus: boolean;
    saveApiKey: boolean;
    testApiKey: boolean;
    assistantGroups: boolean;
    documentAccess: boolean;
    documentAction: boolean;
    documentGroups: boolean;
    auditEvents: boolean;
    curatorFeedback: boolean;
    reviewFeedback: boolean;
    exportFeedback: boolean;
    usageReport: boolean;
    usageLimits: boolean;
    saveUsageLimits: boolean;
    indexStatus: boolean;
    startReindex: boolean;
    archivedConversations: boolean;
    archivedAction: boolean;
  };
  error: string | null;
}

export interface MessageFeedbackState {
  rating: FeedbackRating;
  sending: boolean;
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
  documentAccessByAssistant: {},
  indexStatusByAssistant: {},
  availableGroups: null,
  archivedConversations: [],
  archivedConversationDetail: null,
  auditEvents: [],
  createAssistantModalOpen: false,
  inferAssistantError: null,
  apiKeyStatus: null,
  apiKeyTestResult: null,
  chatStream: null,
  feedbackByMessage: {},
  curatorFeedback: [],
  usageReport: null,
  usageLimits: null,
  notice: null,
  loading: {
    assistants: false,
    createAssistant: false,
    deleteAssistant: false,
    createConversation: false,
    deleteConversation: false,
    uploadDocument: false,
    sendChat: false,
    inferAssistant: false,
    apiKeyStatus: false,
    saveApiKey: false,
    testApiKey: false,
    assistantGroups: false,
    documentAccess: false,
    documentAction: false,
    documentGroups: false,
    auditEvents: false,
    curatorFeedback: false,
    reviewFeedback: false,
    exportFeedback: false,
    usageReport: false,
    usageLimits: false,
    saveUsageLimits: false,
    indexStatus: false,
    startReindex: false,
    archivedConversations: false,
    archivedAction: false
  },
  error: null
};

export const nexusReducer = createReducer(
  initialNexusState,
  on(nexusActions.clearError, (state) => ({ ...state, error: null, notice: null })),
  on(nexusActions.openCreateAssistantModal, (state) => ({
    ...state,
    createAssistantModalOpen: true
  })),
  on(nexusActions.closeCreateAssistantModal, (state) => ({
    ...state,
    createAssistantModalOpen: false
  })),

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
  on(nexusActions.inferAssistantAndSend, (state) => ({
    ...state,
    inferAssistantError: null,
    loading: { ...state.loading, inferAssistant: true },
    error: null
  })),
  on(nexusActions.inferAssistantAndSendSuccess, (state, { assistantId }) => ({
    ...state,
    activeAssistantId: assistantId,
    inferAssistantError: null,
    loading: { ...state.loading, inferAssistant: false }
  })),
  on(nexusActions.inferAssistantAndSendFailure, (state, { error }) => ({
    ...state,
    inferAssistantError: error,
    loading: { ...state.loading, inferAssistant: false }
  })),
  on(nexusActions.clearInferAssistantError, (state) => ({
    ...state,
    inferAssistantError: null
  })),
  on(
    nexusActions.sendChatQuestionSuccess,
    (state, { conversationId, userMessage, assistantMessage }) => {
      const existingMessages = state.messagesByConversation[conversationId] ?? [];
      const conversationHistoryByAssistant = Object.fromEntries(
        Object.entries(state.conversationHistoryByAssistant).map(([assistantId, conversations]) => [
          assistantId,
          conversations.map((conv) => {
            if (conv.id === conversationId && !conv.name) {
              const raw = userMessage.content.trim();
              const name = raw.length > 100 ? raw.slice(0, 97) + "..." : raw;
              return { ...conv, name };
            }
            return conv;
          })
        ])
      );
      return {
        ...state,
        conversationHistoryByAssistant,
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: [...existingMessages, userMessage, assistantMessage]
        },
        chatStream: null,
        loading: { ...state.loading, sendChat: false }
      };
    }
  ),
  on(nexusActions.sendChatQuestionFailure, (state, { error }) => ({
    ...state,
    chatStream: null,
    loading: { ...state.loading, sendChat: false },
    error
  })),
  on(nexusActions.chatStreamStarted, (state, { conversationId, question }) => ({
    ...state,
    chatStream: { conversationId, question, text: "" }
  })),
  on(nexusActions.chatStreamDelta, (state, { text }) =>
    state.chatStream
      ? { ...state, chatStream: { ...state.chatStream, text: state.chatStream.text + text } }
      : state
  ),
  on(nexusActions.chatStreamReplace, (state, { text }) =>
    state.chatStream ? { ...state, chatStream: { ...state.chatStream, text } } : state
  ),

  on(nexusActions.submitFeedback, (state, { messageId, rating }) => ({
    ...state,
    feedbackByMessage: {
      ...state.feedbackByMessage,
      [messageId]: { rating, sending: true, error: null }
    }
  })),
  on(nexusActions.submitFeedbackSuccess, (state, { feedback }) => ({
    ...state,
    feedbackByMessage: {
      ...state.feedbackByMessage,
      [feedback.message_id]: { rating: feedback.rating, sending: false, error: null }
    }
  })),
  on(nexusActions.submitFeedbackFailure, (state, { messageId, error }) => {
    const current = state.feedbackByMessage[messageId];
    if (!current) {
      return state;
    }
    return {
      ...state,
      feedbackByMessage: {
        ...state.feedbackByMessage,
        [messageId]: { ...current, sending: false, error }
      }
    };
  }),

  on(nexusActions.loadCuratorFeedback, (state) => ({
    ...state,
    loading: { ...state.loading, curatorFeedback: true },
    error: null
  })),
  on(nexusActions.loadCuratorFeedbackSuccess, (state, { items }) => ({
    ...state,
    curatorFeedback: items,
    loading: { ...state.loading, curatorFeedback: false }
  })),
  on(nexusActions.loadCuratorFeedbackFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, curatorFeedback: false },
    error
  })),
  on(nexusActions.reviewFeedback, (state) => ({
    ...state,
    loading: { ...state.loading, reviewFeedback: true },
    error: null,
    notice: null
  })),
  on(nexusActions.reviewFeedbackSuccess, (state, { feedback }) => ({
    ...state,
    // Revisada, sai da fila de pendentes.
    curatorFeedback: state.curatorFeedback.filter((item) => item.id !== feedback.id),
    loading: { ...state.loading, reviewFeedback: false },
    notice:
      feedback.status === "validado"
        ? "Avaliação validada: entra no conjunto de referência na próxima exportação."
        : "Avaliação descartada."
  })),
  on(nexusActions.reviewFeedbackFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, reviewFeedback: false },
    error
  })),
  on(nexusActions.exportFeedback, (state) => ({
    ...state,
    loading: { ...state.loading, exportFeedback: true },
    error: null
  })),
  on(nexusActions.exportFeedbackSuccess, (state) => ({
    ...state,
    loading: { ...state.loading, exportFeedback: false }
  })),
  on(nexusActions.exportFeedbackFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, exportFeedback: false },
    error
  })),

  on(nexusActions.loadUsageReport, (state) => ({
    ...state,
    loading: { ...state.loading, usageReport: true },
    error: null
  })),
  on(nexusActions.loadUsageReportSuccess, (state, { report }) => ({
    ...state,
    usageReport: report,
    loading: { ...state.loading, usageReport: false }
  })),
  on(nexusActions.loadUsageReportFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, usageReport: false },
    error
  })),
  on(nexusActions.loadUsageLimits, (state) => ({
    ...state,
    loading: { ...state.loading, usageLimits: true }
  })),
  on(nexusActions.loadUsageLimitsSuccess, (state, { limits }) => ({
    ...state,
    usageLimits: limits,
    loading: { ...state.loading, usageLimits: false }
  })),
  on(nexusActions.loadUsageLimitsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, usageLimits: false },
    error
  })),
  on(nexusActions.saveUsageLimits, (state) => ({
    ...state,
    loading: { ...state.loading, saveUsageLimits: true },
    error: null,
    notice: null
  })),
  on(nexusActions.saveUsageLimitsSuccess, (state, { limits }) => ({
    ...state,
    usageLimits: limits,
    loading: { ...state.loading, saveUsageLimits: false },
    notice: "Limites gravados; valem a partir da próxima pergunta."
  })),
  on(nexusActions.saveUsageLimitsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, saveUsageLimits: false },
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
  })),

  on(nexusActions.setAssistantGroups, (state) => ({
    ...state,
    loading: { ...state.loading, assistantGroups: true },
    error: null
  })),
  on(nexusActions.setAssistantGroupsSuccess, (state, { assistantId, groups }) => ({
    ...state,
    assistants: state.assistants.map((assistant) =>
      assistant.id === assistantId ? { ...assistant, groups } : assistant
    ),
    loading: { ...state.loading, assistantGroups: false }
  })),
  on(nexusActions.setAssistantGroupsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, assistantGroups: false },
    error
  })),

  on(nexusActions.loadDocumentAccess, (state, { background }) =>
    // A consulta periodica nao pisca o aviso nem apaga um erro sendo exibido.
    background
      ? state
      : { ...state, loading: { ...state.loading, documentAccess: true }, error: null }
  ),
  on(nexusActions.loadDocumentAccessSuccess, (state, { assistantId, documents }) => ({
    ...state,
    documentAccessByAssistant: {
      ...state.documentAccessByAssistant,
      [assistantId]: documents
    },
    loading: { ...state.loading, documentAccess: false }
  })),
  on(nexusActions.loadDocumentAccessFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, documentAccess: false },
    error
  })),

  on(nexusActions.setDocumentGroups, (state) => ({
    ...state,
    loading: { ...state.loading, documentGroups: true },
    error: null
  })),
  on(nexusActions.setDocumentGroupsSuccess, (state, { document }) => ({
    ...state,
    documentAccessByAssistant: {
      ...state.documentAccessByAssistant,
      [document.assistant_id]: (
        state.documentAccessByAssistant[document.assistant_id] ?? []
      ).map((item) => (item.id === document.id ? document : item))
    },
    loading: { ...state.loading, documentGroups: false }
  })),
  on(nexusActions.setDocumentGroupsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, documentGroups: false },
    error
  })),

  on(
    nexusActions.deleteDocument,
    nexusActions.replaceDocument,
    nexusActions.reprocessDocument,
    (state) => ({
      ...state,
      loading: { ...state.loading, documentAction: true },
      error: null
    })
  ),
  on(nexusActions.deleteDocumentSuccess, (state, { assistantId, documentId }) => ({
    ...state,
    documentAccessByAssistant: {
      ...state.documentAccessByAssistant,
      // A nova versao pendente sai junto com a vigente (RF-50).
      [assistantId]: (state.documentAccessByAssistant[assistantId] ?? []).filter(
        (item) => item.id !== documentId && item.replaces_document_id !== documentId
      )
    },
    loading: { ...state.loading, documentAction: false }
  })),
  on(
    nexusActions.replaceDocumentSuccess,
    nexusActions.reprocessDocumentSuccess,
    (state, { document }) => ({
      ...state,
      documentAccessByAssistant: {
        ...state.documentAccessByAssistant,
        [document.assistant_id]: upsertDocument(
          state.documentAccessByAssistant[document.assistant_id] ?? [],
          document
        )
      },
      loading: { ...state.loading, documentAction: false }
    })
  ),
  on(
    nexusActions.deleteDocumentFailure,
    nexusActions.replaceDocumentFailure,
    nexusActions.reprocessDocumentFailure,
    (state, { error }) => ({
      ...state,
      loading: { ...state.loading, documentAction: false },
      error
    })
  ),

  on(nexusActions.loadIndexStatus, (state, { background }) =>
    background
      ? state
      : { ...state, loading: { ...state.loading, indexStatus: true } }
  ),
  on(nexusActions.loadIndexStatusSuccess, (state, { status }) => ({
    ...state,
    indexStatusByAssistant: {
      ...state.indexStatusByAssistant,
      [status.assistant_id]: status
    },
    loading: { ...state.loading, indexStatus: false }
  })),
  on(nexusActions.loadIndexStatusFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, indexStatus: false },
    error
  })),
  on(nexusActions.startReindex, (state) => ({
    ...state,
    loading: { ...state.loading, startReindex: true },
    error: null
  })),
  on(nexusActions.startReindexSuccess, (state, { job }) => {
    const current = state.indexStatusByAssistant[job.assistant_id];
    return {
      ...state,
      indexStatusByAssistant: current
        ? {
            ...state.indexStatusByAssistant,
            [job.assistant_id]: { ...current, last_reindex: job }
          }
        : state.indexStatusByAssistant,
      loading: { ...state.loading, startReindex: false }
    };
  }),
  on(nexusActions.startReindexFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, startReindex: false },
    error
  })),

  on(nexusActions.loadAvailableGroupsSuccess, (state, { groups }) => ({
    ...state,
    availableGroups: groups
  })),
  on(nexusActions.loadAvailableGroupsFailure, (state) => ({
    ...state,
    availableGroups: null
  })),
  on(nexusActions.loadArchivedConversations, (state) => ({
    ...state,
    loading: { ...state.loading, archivedConversations: true },
    error: null
  })),
  on(nexusActions.loadArchivedConversationsSuccess, (state, { conversations }) => ({
    ...state,
    archivedConversations: conversations,
    loading: { ...state.loading, archivedConversations: false }
  })),
  on(nexusActions.loadArchivedConversationsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, archivedConversations: false },
    error
  })),
  on(nexusActions.openArchivedConversation, nexusActions.deleteArchivedConversation, (state) => ({
    ...state,
    loading: { ...state.loading, archivedAction: true },
    error: null
  })),
  on(nexusActions.openArchivedConversationSuccess, (state, { conversation }) => ({
    ...state,
    archivedConversationDetail: conversation,
    loading: { ...state.loading, archivedAction: false }
  })),
  on(nexusActions.closeArchivedConversation, (state) => ({
    ...state,
    archivedConversationDetail: null
  })),
  on(nexusActions.deleteArchivedConversationSuccess, (state, { conversationId }) => ({
    ...state,
    archivedConversations: state.archivedConversations.filter(
      (item) => item.id !== conversationId
    ),
    archivedConversationDetail:
      state.archivedConversationDetail?.id === conversationId
        ? null
        : state.archivedConversationDetail,
    loading: { ...state.loading, archivedAction: false }
  })),
  on(
    nexusActions.openArchivedConversationFailure,
    nexusActions.deleteArchivedConversationFailure,
    (state, { error }) => ({
      ...state,
      loading: { ...state.loading, archivedAction: false },
      error
    })
  ),

  on(nexusActions.loadAuditEvents, (state) => ({
    ...state,
    loading: { ...state.loading, auditEvents: true },
    error: null
  })),
  on(nexusActions.loadAuditEventsSuccess, (state, { events }) => ({
    ...state,
    auditEvents: events,
    loading: { ...state.loading, auditEvents: false }
  })),
  on(nexusActions.loadAuditEventsFailure, (state, { error }) => ({
    ...state,
    loading: { ...state.loading, auditEvents: false },
    error
  }))
);

function upsertDocument(
  documents: readonly DocumentAccess[],
  document: DocumentAccess
): DocumentAccess[] {
  return documents.some((item) => item.id === document.id)
    ? documents.map((item) => (item.id === document.id ? document : item))
    : [document, ...documents];
}
