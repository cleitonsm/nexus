import { createFeatureSelector, createSelector } from "@ngrx/store";

import { LlmConfigState, llmConfigFeatureKey } from "./llm-config.reducer";

export const selectLlmConfigState = createFeatureSelector<LlmConfigState>(llmConfigFeatureKey);

export const selectLlmCredentials = createSelector(
  selectLlmConfigState,
  (state) => state.credentials
);

export const selectDefaultLlmCredential = createSelector(
  selectLlmCredentials,
  (credentials) => credentials.find((item) => item.is_default) ?? null
);

export const selectLlmProviderUrls = createSelector(
  selectLlmConfigState,
  (state) => state.providerUrls
);

export const selectLlmCurrency = createSelector(selectLlmConfigState, (state) => state.currency);

export const selectLlmOptions = createSelector(selectLlmConfigState, (state) => state.options);

export const selectDefaultLlmOption = createSelector(
  selectLlmOptions,
  (options) => options.find((item) => item.is_default) ?? null
);

export const selectAssistantLlmById = createSelector(
  selectLlmConfigState,
  (state) => state.assistantLlm
);

export const selectAssistantRetrievalById = createSelector(
  selectLlmConfigState,
  (state) => state.assistantRetrieval
);

export const selectDefaultImpact = createSelector(selectLlmConfigState, (state) => state.impact);

export const selectLlmTestResult = createSelector(
  selectLlmConfigState,
  (state) => state.testResult
);

export const selectLlmSavedCount = createSelector(
  selectLlmConfigState,
  (state) => state.savedCount
);

export const selectLlmNotice = createSelector(selectLlmConfigState, (state) => state.notice);

export const selectLlmLoading = createSelector(selectLlmConfigState, (state) => state.loading);

export const selectLlmError = createSelector(selectLlmConfigState, (state) => state.error);

export const selectLlmConflict = createSelector(selectLlmConfigState, (state) => state.conflict);
