import { createActionGroup, emptyProps, props } from "@ngrx/store";

import {
  AssistantLlm,
  AssistantLlmInput,
  AssistantRetrieval,
  AssistantRetrievalInput,
  DefaultChangeImpact,
  LlmCredential,
  LlmCredentialConflict,
  LlmCredentialInput,
  LlmCredentialList,
  LlmCredentialOption,
  LlmCredentialTestResult
} from "../shared/models/nexus.models";

/** SPEC-013: credenciais de LLM e configuracao por assistente. */
export const llmConfigActions = createActionGroup({
  source: "LLM Config",
  events: {
    "Clear Feedback": emptyProps(),

    "Load Credentials": emptyProps(),
    "Load Credentials Success": props<{ list: LlmCredentialList }>(),
    "Load Credentials Failure": props<{ error: string }>(),
    "Create Credential": props<{ input: LlmCredentialInput }>(),
    "Create Credential Success": props<{ credential: LlmCredential }>(),
    "Update Credential": props<{ id: string; input: LlmCredentialInput }>(),
    "Update Credential Success": props<{ credential: LlmCredential }>(),
    "Delete Credential": props<{ id: string }>(),
    "Delete Credential Success": props<{ id: string }>(),
    "Set Default Credential": props<{ id: string }>(),
    "Set Default Credential Success": props<{ credential: LlmCredential }>(),
    /** Falha de qualquer alteracao de credencial; ``conflict`` no 409 da RN-38. */
    "Credential Change Failure": props<{
      error: string;
      conflict: LlmCredentialConflict | null;
    }>(),

    "Load Default Impact": props<{ id: string; modelNames: string[] | null }>(),
    "Load Default Impact Success": props<{ impact: DefaultChangeImpact }>(),
    "Load Default Impact Failure": props<{ error: string }>(),
    "Clear Default Impact": emptyProps(),

    "Test Credential": props<{ id: string; model: string | null }>(),
    "Test Credential Success": props<{ result: LlmCredentialTestResult }>(),
    "Test Credential Failure": props<{ error: string }>(),

    "Load Options": emptyProps(),
    "Load Options Success": props<{ options: LlmCredentialOption[] }>(),
    "Load Options Failure": props<{ error: string }>(),

    "Load Assistant Llm": props<{ assistantId: string }>(),
    "Load Assistant Llm Success": props<{ assistantId: string; llm: AssistantLlm }>(),
    "Load Assistant Llm Failure": props<{ error: string }>(),
    "Save Assistant Llm": props<{ assistantId: string; input: AssistantLlmInput }>(),
    "Save Assistant Llm Success": props<{ assistantId: string; llm: AssistantLlm }>(),
    "Save Assistant Llm Failure": props<{ error: string }>(),

    "Load Assistant Retrieval": props<{ assistantId: string }>(),
    "Load Assistant Retrieval Success": props<{
      assistantId: string;
      retrieval: AssistantRetrieval;
    }>(),
    "Load Assistant Retrieval Failure": props<{ error: string }>(),
    "Save Assistant Retrieval": props<{ assistantId: string; input: AssistantRetrievalInput }>(),
    "Save Assistant Retrieval Success": props<{
      assistantId: string;
      retrieval: AssistantRetrieval;
    }>(),
    "Save Assistant Retrieval Failure": props<{ error: string }>()
  }
});
