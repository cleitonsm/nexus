import { createFeatureSelector, createSelector } from "@ngrx/store";

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

export const selectActiveAssistantConversations = createSelector(selectNexusState, (state) => {
  if (!state.activeAssistantId) {
    return [];
  }
  return state.conversationHistoryByAssistant[state.activeAssistantId] ?? [];
});

export const selectDocuments = createSelector(selectNexusState, (state) => state.documents);

export const selectError = createSelector(selectNexusState, (state) => state.error);

export const selectApiKeyStatus = createSelector(
  selectNexusState,
  (state) => state.apiKeyStatus
);

export const selectLoadingState = createSelector(
  selectNexusState,
  (state) => state.loading
);
