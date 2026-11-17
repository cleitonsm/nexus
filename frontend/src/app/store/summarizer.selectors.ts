import { createFeatureSelector, createSelector } from "@ngrx/store";

import { SummarizerState, summarizerFeatureKey } from "./summarizer.reducer";

export const selectSummarizerState = createFeatureSelector<SummarizerState>(summarizerFeatureKey);

export const selectSummarizerInfo = createSelector(selectSummarizerState, (state) => state.info);

export const selectSummaryDocuments = createSelector(
  selectSummarizerState,
  (state) => state.documents
);

export const selectSummarizerUploading = createSelector(
  selectSummarizerState,
  (state) => state.uploading
);

export const selectSummarizerUploadingName = createSelector(
  selectSummarizerState,
  (state) => state.uploadingName
);

export const selectSummarizerError = createSelector(selectSummarizerState, (state) => state.error);
