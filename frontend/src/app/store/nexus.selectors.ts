import { createFeatureSelector, createSelector } from "@ngrx/store";

import { Citation } from "../shared/models/nexus.models";
import { NexusState, nexusFeatureKey } from "./nexus.reducer";

export const selectNexusState = createFeatureSelector<NexusState>(nexusFeatureKey);

export const selectAssistants = createSelector(
  selectNexusState,
  (state) => state.assistants
);

export const selectActiveAssistantId = createSelector(
  selectNexusState,
  (state) => state.activeAssistantId
);

export const selectConversationsByAssistant = createSelector(
  selectNexusState,
  (state) => state.conversationHistoryByAssistant
);

export const selectCurrentConversationId = createSelector(
  selectNexusState,
  (state) => state.currentConversationId
);

export const selectCurrentMessages = createSelector(selectNexusState, (state) => {
  if (!state.currentConversationId) {
    return [];
  }
  return state.messagesByConversation[state.currentConversationId] ?? [];
});

/** Fontes de cada resposta da conversa atual, por id da mensagem (RF-38). */
export const selectCurrentCitationsByMessage = createSelector(
  selectCurrentMessages,
  (messages): Record<string, Citation[]> =>
    Object.fromEntries(
      messages
        .filter((message) => (message.citations?.length ?? 0) > 0)
        .map((message) => [
          message.id,
          [...(message.citations ?? [])].sort((left, right) => left.number - right.number)
        ])
    )
);

export const selectActiveAssistantConversations = createSelector(selectNexusState, (state) => {
  if (!state.activeAssistantId) {
    return [];
  }
  return state.conversationHistoryByAssistant[state.activeAssistantId] ?? [];
});

export const selectDocuments = createSelector(selectNexusState, (state) => state.documents);
export const selectCreateAssistantModalOpen = createSelector(
  selectNexusState,
  (state) => state.createAssistantModalOpen
);

export const selectInferAssistantError = createSelector(
  selectNexusState,
  (state) => state.inferAssistantError
);

export const selectError = createSelector(selectNexusState, (state) => state.error);

export const selectApiKeyStatus = createSelector(
  selectNexusState,
  (state) => state.apiKeyStatus
);

export const selectApiKeyTestResult = createSelector(
  selectNexusState,
  (state) => state.apiKeyTestResult
);

export const selectLoadingState = createSelector(
  selectNexusState,
  (state) => state.loading
);
