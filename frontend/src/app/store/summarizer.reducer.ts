import { createReducer, on } from "@ngrx/store";

import { SummarizerInfo, SummaryDocument } from "../shared/models/nexus.models";
import { summarizerActions } from "./summarizer.actions";

export const summarizerFeatureKey = "summarizer";

export interface SummarizerState {
  info: SummarizerInfo | null;
  /** Documento por conversa; ``null`` = conversa conferida e sem documento. */
  documents: Record<string, SummaryDocument | null>;
  uploading: boolean;
  /** Nome do arquivo em envio: a tela mostra o cartao antes da resposta da API. */
  uploadingName: string | null;
  error: string | null;
}

export const initialSummarizerState: SummarizerState = {
  info: null,
  documents: {},
  uploading: false,
  uploadingName: null,
  error: null
};

function withDocument(state: SummarizerState, document: SummaryDocument): SummarizerState {
  return { ...state, documents: { ...state.documents, [document.conversation_id]: document } };
}

export const summarizerReducer = createReducer(
  initialSummarizerState,
  on(summarizerActions.loadInfoSuccess, (state, { info }) => ({ ...state, info })),
  on(summarizerActions.uploadDocument, (state, { file }) => ({
    ...state,
    uploading: true,
    uploadingName: file.name,
    error: null
  })),
  on(summarizerActions.uploadDocumentSuccess, (state, { document }) => ({
    ...withDocument(state, document),
    uploading: false,
    uploadingName: null
  })),
  on(summarizerActions.uploadDocumentFailure, (state, { error }) => ({
    ...state,
    uploading: false,
    uploadingName: null,
    error
  })),
  on(summarizerActions.loadDocumentSuccess, (state, { conversationId, document }) => ({
    ...state,
    documents: { ...state.documents, [conversationId]: document }
  })),
  on(summarizerActions.retrySummarySuccess, (state, { document }) => withDocument(state, document)),
  on(summarizerActions.retrySummaryFailure, (state, { error }) => ({ ...state, error })),
  on(summarizerActions.clearError, (state) => ({ ...state, error: null }))
);
