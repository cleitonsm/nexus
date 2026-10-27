import "@angular/compiler";
import { describe, expect, it } from "vitest";

import {
  AssistantRetrieval,
  LlmCredential,
  LlmCredentialList
} from "../shared/models/nexus.models";
import { llmConfigActions } from "./llm-config.actions";
import { initialLlmConfigState, llmConfigReducer } from "./llm-config.reducer";
import {
  selectAssistantRetrievalById,
  selectDefaultLlmCredential,
  selectLlmConflict,
  selectLlmCredentials
} from "./llm-config.selectors";

function credential(overrides: Partial<LlmCredential> = {}): LlmCredential {
  return {
    id: "c1",
    name: "OpenAI",
    provider: "openai",
    api_url: "https://api.openai.com/v1/chat/completions",
    models: [{ name: "gpt-4o-mini", input_per_1k: null, output_per_1k: null }],
    default_model: "gpt-4o-mini",
    is_default: true,
    key_configured: true,
    assistant_ids: [],
    following_assistant_ids: ["a1"],
    ...overrides
  };
}

const LIST: LlmCredentialList = {
  items: [credential(), credential({ id: "c2", name: "Gemini", provider: "gemini", is_default: false })],
  provider_urls: { openai: "https://api.openai.com/v1/chat/completions" },
  currency: "USD"
};

const RETRIEVAL: AssistantRetrieval = {
  hybrid_enabled: { stored: false, effective: false, origin: "assistant" },
  candidates: { stored: null, effective: 30, origin: "default" },
  top_k: { stored: null, effective: 5, origin: "default" },
  min_score: { stored: 0.3, effective: 0.3, origin: "assistant" },
  top_k_clamped: false,
  limits: { candidates: [5, 100], top_k: [1, 20], min_score: [0, 1] }
};

describe("llmConfig reducer (SPEC-013, CT-110)", () => {
  it("stores the credential list, presets and currency", () => {
    let state = llmConfigReducer(initialLlmConfigState, llmConfigActions.loadCredentials());
    expect(state.loading.credentials).toBe(true);
    state = llmConfigReducer(state, llmConfigActions.loadCredentialsSuccess({ list: LIST }));
    expect(state.loading.credentials).toBe(false);
    expect(selectLlmCredentials.projector(state)).toHaveLength(2);
    expect(selectDefaultLlmCredential.projector(LIST.items)?.id).toBe("c1");
    expect(state.currency).toBe("USD");
  });

  it("counts saved credentials so the form can close, and clears the test result", () => {
    let state = llmConfigReducer(
      {
        ...initialLlmConfigState,
        testResult: { ok: true, credential_id: "c1", model: "m", message: "ok", response_preview: "OK" }
      },
      llmConfigActions.createCredential({
        input: {
          name: "x",
          provider: "openai",
          api_url: null,
          models: [],
          default_model: "m",
          api_key: "chave-ficticia"
        }
      })
    );
    expect(state.loading.saveCredential).toBe(true);
    state = llmConfigReducer(state, llmConfigActions.createCredentialSuccess({ credential: credential() }));
    expect(state.loading.saveCredential).toBe(false);
    expect(state.savedCount).toBe(1);
    expect(state.testResult).toBeNull();
  });

  it("keeps the 409 conflict for the screen and clears it on the next attempt", () => {
    const conflict = {
      message: "the default credential cannot be removed.",
      assistant_ids: ["a1"],
      models: [],
      is_default: true
    };
    let state = llmConfigReducer(initialLlmConfigState, llmConfigActions.deleteCredential({ id: "c1" }));
    state = llmConfigReducer(
      state,
      llmConfigActions.credentialChangeFailure({ error: conflict.message, conflict })
    );
    expect(selectLlmConflict.projector(state)).toEqual(conflict);
    expect(state.loading.saveCredential).toBe(false);
    state = llmConfigReducer(state, llmConfigActions.setDefaultCredential({ id: "c2" }));
    expect(state.conflict).toBeNull();
    expect(state.error).toBeNull();
  });

  it("removes a deleted credential at once", () => {
    const loaded = llmConfigReducer(initialLlmConfigState, llmConfigActions.loadCredentialsSuccess({ list: LIST }));
    const state = llmConfigReducer(loaded, llmConfigActions.deleteCredentialSuccess({ id: "c2" }));
    expect(state.credentials.map((item) => item.id)).toEqual(["c1"]);
  });

  it("keeps the D11 impact until it is cleared", () => {
    let state = llmConfigReducer(
      initialLlmConfigState,
      llmConfigActions.loadDefaultImpact({ id: "c2", modelNames: null })
    );
    expect(state.loading.impact).toBe(true);
    state = llmConfigReducer(
      state,
      llmConfigActions.loadDefaultImpactSuccess({
        impact: { credential_id: "c2", following_assistant_ids: ["a1"], falling_back_assistant_ids: ["a1"] }
      })
    );
    expect(state.impact?.falling_back_assistant_ids).toEqual(["a1"]);
    state = llmConfigReducer(state, llmConfigActions.clearDefaultImpact());
    expect(state.impact).toBeNull();
  });

  it("stores the assistant configuration per assistant with a notice on save", () => {
    let state = llmConfigReducer(
      initialLlmConfigState,
      llmConfigActions.loadAssistantRetrievalSuccess({ assistantId: "a1", retrieval: RETRIEVAL })
    );
    expect(selectAssistantRetrievalById.projector(state)["a1"]?.min_score.effective).toBe(0.3);
    state = llmConfigReducer(
      state,
      llmConfigActions.saveAssistantRetrieval({
        assistantId: "a1",
        input: { hybrid_enabled: null, candidates: null, top_k: null, min_score: null }
      })
    );
    expect(state.loading.saveAssistantRetrieval).toBe(true);
    state = llmConfigReducer(
      state,
      llmConfigActions.saveAssistantRetrievalSuccess({ assistantId: "a1", retrieval: RETRIEVAL })
    );
    expect(state.notice).toContain("próxima pergunta");
    state = llmConfigReducer(
      state,
      llmConfigActions.saveAssistantLlmFailure({ error: "model 'x' is not allowed by the credential." })
    );
    expect(state.error).toContain("not allowed");
    state = llmConfigReducer(state, llmConfigActions.clearFeedback());
    expect(state.error).toBeNull();
    expect(state.notice).toBeNull();
  });
});
