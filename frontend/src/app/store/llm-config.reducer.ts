import { createReducer, on } from "@ngrx/store";

import {
  AssistantLlm,
  AssistantRetrieval,
  DefaultChangeImpact,
  LlmCredential,
  LlmCredentialConflict,
  LlmCredentialOption,
  LlmCredentialTestResult
} from "../shared/models/nexus.models";
import { llmConfigActions } from "./llm-config.actions";

export const llmConfigFeatureKey = "llmConfig";

export interface LlmConfigState {
  credentials: LlmCredential[];
  providerUrls: Record<string, string>;
  currency: string;
  options: LlmCredentialOption[];
  assistantLlm: Record<string, AssistantLlm>;
  assistantRetrieval: Record<string, AssistantRetrieval>;
  impact: DefaultChangeImpact | null;
  testResult: LlmCredentialTestResult | null;
  /** Incrementa a cada credencial gravada: a tela fecha o formulario. */
  savedCount: number;
  /** Mensagem de sucesso curta (configuracao do assistente gravada). */
  notice: string | null;
  loading: {
    credentials: boolean;
    saveCredential: boolean;
    impact: boolean;
    test: boolean;
    options: boolean;
    assistantLlm: boolean;
    saveAssistantLlm: boolean;
    assistantRetrieval: boolean;
    saveAssistantRetrieval: boolean;
  };
  error: string | null;
  conflict: LlmCredentialConflict | null;
}

export const initialLlmConfigState: LlmConfigState = {
  credentials: [],
  providerUrls: {},
  currency: "USD",
  options: [],
  assistantLlm: {},
  assistantRetrieval: {},
  impact: null,
  testResult: null,
  savedCount: 0,
  notice: null,
  loading: {
    credentials: false,
    saveCredential: false,
    impact: false,
    test: false,
    options: false,
    assistantLlm: false,
    saveAssistantLlm: false,
    assistantRetrieval: false,
    saveAssistantRetrieval: false
  },
  error: null,
  conflict: null
};

type LoadingKey = keyof LlmConfigState["loading"];

function loading(state: LlmConfigState, key: LoadingKey, value: boolean): LlmConfigState["loading"] {
  return { ...state.loading, [key]: value };
}

function started(state: LlmConfigState, key: LoadingKey): LlmConfigState {
  return { ...state, loading: loading(state, key, true), error: null, conflict: null, notice: null };
}

function failed(state: LlmConfigState, key: LoadingKey, error: string): LlmConfigState {
  return { ...state, loading: loading(state, key, false), error };
}

function credentialSaved(state: LlmConfigState): LlmConfigState {
  return {
    ...state,
    loading: loading(state, "saveCredential", false),
    savedCount: state.savedCount + 1,
    impact: null,
    testResult: null
  };
}

export const llmConfigReducer = createReducer(
  initialLlmConfigState,
  on(llmConfigActions.clearFeedback, (state) => ({
    ...state,
    error: null,
    conflict: null,
    notice: null,
    testResult: null
  })),

  on(llmConfigActions.loadCredentials, (state) => ({
    ...state,
    loading: loading(state, "credentials", true)
  })),
  on(llmConfigActions.loadCredentialsSuccess, (state, { list }) => ({
    ...state,
    credentials: list.items,
    providerUrls: list.provider_urls,
    currency: list.currency,
    loading: loading(state, "credentials", false)
  })),
  on(llmConfigActions.loadCredentialsFailure, (state, { error }) =>
    failed(state, "credentials", error)
  ),

  on(
    llmConfigActions.createCredential,
    llmConfigActions.updateCredential,
    llmConfigActions.deleteCredential,
    llmConfigActions.setDefaultCredential,
    (state) => started(state, "saveCredential")
  ),
  on(
    llmConfigActions.createCredentialSuccess,
    llmConfigActions.updateCredentialSuccess,
    llmConfigActions.setDefaultCredentialSuccess,
    (state) => credentialSaved(state)
  ),
  on(llmConfigActions.deleteCredentialSuccess, (state, { id }) => ({
    ...credentialSaved(state),
    credentials: state.credentials.filter((item) => item.id !== id)
  })),
  on(llmConfigActions.credentialChangeFailure, (state, { error, conflict }) => ({
    ...failed(state, "saveCredential", error),
    conflict
  })),

  on(llmConfigActions.loadDefaultImpact, (state) => ({
    ...state,
    impact: null,
    loading: loading(state, "impact", true)
  })),
  on(llmConfigActions.loadDefaultImpactSuccess, (state, { impact }) => ({
    ...state,
    impact,
    loading: loading(state, "impact", false)
  })),
  on(llmConfigActions.loadDefaultImpactFailure, (state, { error }) =>
    failed(state, "impact", error)
  ),
  on(llmConfigActions.clearDefaultImpact, (state) => ({ ...state, impact: null })),

  on(llmConfigActions.testCredential, (state) => ({
    ...started(state, "test"),
    testResult: null
  })),
  on(llmConfigActions.testCredentialSuccess, (state, { result }) => ({
    ...state,
    testResult: result,
    loading: loading(state, "test", false)
  })),
  on(llmConfigActions.testCredentialFailure, (state, { error }) => failed(state, "test", error)),

  on(llmConfigActions.loadOptions, (state) => ({
    ...state,
    loading: loading(state, "options", true)
  })),
  on(llmConfigActions.loadOptionsSuccess, (state, { options }) => ({
    ...state,
    options,
    loading: loading(state, "options", false)
  })),
  on(llmConfigActions.loadOptionsFailure, (state, { error }) => failed(state, "options", error)),

  on(llmConfigActions.loadAssistantLlm, (state) => ({
    ...state,
    loading: loading(state, "assistantLlm", true)
  })),
  on(llmConfigActions.loadAssistantLlmSuccess, (state, { assistantId, llm }) => ({
    ...state,
    assistantLlm: { ...state.assistantLlm, [assistantId]: llm },
    loading: loading(state, "assistantLlm", false)
  })),
  on(llmConfigActions.loadAssistantLlmFailure, (state, { error }) =>
    failed(state, "assistantLlm", error)
  ),
  on(llmConfigActions.saveAssistantLlm, (state) => started(state, "saveAssistantLlm")),
  on(llmConfigActions.saveAssistantLlmSuccess, (state, { assistantId, llm }) => ({
    ...state,
    assistantLlm: { ...state.assistantLlm, [assistantId]: llm },
    loading: loading(state, "saveAssistantLlm", false),
    notice: "Modelo de linguagem do assistente gravado."
  })),
  on(llmConfigActions.saveAssistantLlmFailure, (state, { error }) =>
    failed(state, "saveAssistantLlm", error)
  ),

  on(llmConfigActions.loadAssistantRetrieval, (state) => ({
    ...state,
    loading: loading(state, "assistantRetrieval", true)
  })),
  on(llmConfigActions.loadAssistantRetrievalSuccess, (state, { assistantId, retrieval }) => ({
    ...state,
    assistantRetrieval: { ...state.assistantRetrieval, [assistantId]: retrieval },
    loading: loading(state, "assistantRetrieval", false)
  })),
  on(llmConfigActions.loadAssistantRetrievalFailure, (state, { error }) =>
    failed(state, "assistantRetrieval", error)
  ),
  on(llmConfigActions.saveAssistantRetrieval, (state) => started(state, "saveAssistantRetrieval")),
  on(llmConfigActions.saveAssistantRetrievalSuccess, (state, { assistantId, retrieval }) => ({
    ...state,
    assistantRetrieval: { ...state.assistantRetrieval, [assistantId]: retrieval },
    loading: loading(state, "saveAssistantRetrieval", false),
    notice: "Parâmetros de recuperação gravados. Valem a partir da próxima pergunta."
  })),
  on(llmConfigActions.saveAssistantRetrievalFailure, (state, { error }) =>
    failed(state, "saveAssistantRetrieval", error)
  )
);
