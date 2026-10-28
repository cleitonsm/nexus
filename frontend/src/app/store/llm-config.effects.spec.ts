/**
 * SPEC-013 (CT-110): effects das credenciais com a API simulada, sem TestBed.
 */
import { Actions } from "@ngrx/effects";
import { Observable, Subject, of, throwError } from "rxjs";
import { describe, expect, it, vi } from "vitest";

import { NexusApiService } from "../core/services/nexus-api.service";
import { llmConfigActions } from "./llm-config.actions";
import {
  deleteLlmCredentialEffect,
  reloadLlmCredentialsEffect,
  saveAssistantRetrievalEffect,
  testLlmCredentialEffect
} from "./llm-config.effects";

function collect<T>(source: Observable<T>): T[] {
  const received: T[] = [];
  source.subscribe((value) => received.push(value));
  return received;
}

function actionsOf(stream: Subject<unknown>): Actions {
  return new Actions(stream as Observable<never>);
}

function api(overrides: Record<string, unknown>): NexusApiService {
  return overrides as unknown as NexusApiService;
}

describe("llmConfig effects (SPEC-013, CT-110)", () => {
  it("turns the RN-38 409 into a conflict the screen can explain", () => {
    const stream = new Subject<unknown>();
    const conflict = {
      status: 409,
      error: {
        detail: {
          code: "llm_credential_in_use",
          message: "the credential is used by assistants.",
          assistant_ids: ["a1"],
          models: [],
          is_default: false
        }
      }
    };
    const received = collect(
      deleteLlmCredentialEffect(
        actionsOf(stream),
        api({ deleteLlmCredential: vi.fn(() => throwError(() => conflict)) })
      )
    );
    stream.next(llmConfigActions.deleteCredential({ id: "c2" }));
    expect(received).toHaveLength(1);
    const action = received[0] as ReturnType<typeof llmConfigActions.credentialChangeFailure>;
    expect(action.type).toBe(llmConfigActions.credentialChangeFailure.type);
    expect(action.conflict?.assistant_ids).toEqual(["a1"]);
  });

  it("reloads the list after any change, because the default and users change too", () => {
    const stream = new Subject<unknown>();
    const received = collect(reloadLlmCredentialsEffect(actionsOf(stream)));
    stream.next(llmConfigActions.deleteCredentialSuccess({ id: "c2" }));
    stream.next(
      llmConfigActions.setDefaultCredentialSuccess({
        credential: {
          id: "c1",
          name: "OpenAI",
          provider: "openai",
          api_url: "https://api.openai.com/v1/chat/completions",
          models: [],
          default_model: "m",
          is_default: true,
          key_configured: true,
          assistant_ids: [],
          following_assistant_ids: []
        }
      })
    );
    expect(received.map((action) => (action as { type: string }).type)).toEqual([
      llmConfigActions.loadCredentials.type,
      llmConfigActions.loadCredentials.type
    ]);
  });

  it("sends the chosen model to the test and reads the server message on failure", () => {
    const stream = new Subject<unknown>();
    const test = vi.fn(() =>
      throwError(() => ({
        status: 503,
        error: { detail: { code: "llm_credential_key_unreadable", message: "A chave gravada não pôde ser decifrada." } }
      }))
    );
    const received = collect(testLlmCredentialEffect(actionsOf(stream), api({ testLlmCredential: test })));
    stream.next(llmConfigActions.testCredential({ id: "c1", model: "gpt-4o" }));
    expect(test).toHaveBeenCalledWith("c1", "gpt-4o");
    expect((received[0] as { error: string }).error).toContain("decifrada");
  });

  it("saves the retrieval profile for the right assistant", () => {
    const stream = new Subject<unknown>();
    const save = vi.fn((_assistantId: string, _input: unknown) => of({ top_k_clamped: false }));
    const received = collect(
      saveAssistantRetrievalEffect(actionsOf(stream), api({ saveAssistantRetrieval: save }))
    );
    const input = { hybrid_enabled: false, candidates: null, top_k: 8, min_score: null };
    stream.next(llmConfigActions.saveAssistantRetrieval({ assistantId: "a1", input }));
    expect(save).toHaveBeenCalledWith("a1", input);
    expect((received[0] as { assistantId: string }).assistantId).toBe("a1");
  });
});
