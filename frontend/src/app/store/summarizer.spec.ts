/**
 * SPEC-018: CT-150, estado e effects do resumidor (RF-114, RF-115, D31, D36).
 * Effects funcionais com a API e o Store simulados, sem TestBed.
 */
import { HttpErrorResponse } from "@angular/common/http";
import { Actions } from "@ngrx/effects";
import { Store } from "@ngrx/store";
import { Observable, Subject, of, throwError } from "rxjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NexusApiService } from "../core/services/nexus-api.service";
import { SummaryDocument } from "../shared/models/nexus.models";
import { SUMMARY_POLL_INTERVAL_MS } from "../shared/summarizer/summarizer";
import { nexusActions } from "./nexus.actions";
import { summarizerActions } from "./summarizer.actions";
import {
  loadSummaryDocumentEffect,
  pollSummaryDocumentEffect,
  reloadMessagesWhenSummaryReadyEffect,
  uploadSummaryDocumentEffect
} from "./summarizer.effects";
import { initialSummarizerState, summarizerReducer } from "./summarizer.reducer";

function doc(overrides: Partial<SummaryDocument> = {}): SummaryDocument {
  return {
    document_id: "d1",
    conversation_id: "c1",
    source_name: "contrato.pdf",
    size_bytes: 10,
    stage: "enviado",
    done: 0,
    total: 0,
    failure_code: null,
    failure_detail: null,
    questions_available: false,
    created_at: "2026-10-30T12:00:00Z",
    expires_at: null,
    ...overrides
  };
}

function collect<T>(source: Observable<T>): T[] {
  const received: T[] = [];
  source.subscribe((value) => received.push(value));
  return received;
}

const FILE = new File(["texto"], "contrato.pdf");

describe("summarizerReducer (CT-150)", () => {
  it("keeps the document per conversation and the upload flag", () => {
    let state = summarizerReducer(
      initialSummarizerState,
      summarizerActions.uploadDocument({ conversationId: "c1", assistantId: "sys", file: FILE })
    );
    expect(state.uploading).toBe(true);
    state = summarizerReducer(state, summarizerActions.uploadDocumentSuccess({ document: doc() }));
    expect(state.documents["c1"]?.stage).toBe("enviado");
    expect(state.uploading).toBe(false);
    state = summarizerReducer(
      state,
      summarizerActions.loadDocumentSuccess({ conversationId: "c2", document: null, previousStage: null })
    );
    expect(state.documents["c2"]).toBeNull();
  });

  it("keeps the error until cleared", () => {
    let state = summarizerReducer(
      initialSummarizerState,
      summarizerActions.uploadDocumentFailure({ error: "limite" })
    );
    expect(state.error).toBe("limite");
    state = summarizerReducer(state, summarizerActions.clearError());
    expect(state.error).toBeNull();
  });
});

describe("summarizer effects (CT-150)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("creates the summarizer conversation before uploading (D7)", () => {
    const api = {
      createConversation: vi.fn(() => of({ id: "nova", assistant_id: "sys" })),
      uploadConversationDocument: vi.fn(() => of(doc({ conversation_id: "nova" })))
    } as unknown as NexusApiService;
    const actions = new Subject<unknown>();
    const received = collect(uploadSummaryDocumentEffect(actions as unknown as Actions, api));
    actions.next(summarizerActions.uploadDocument({ conversationId: null, assistantId: "sys", file: FILE }));
    expect(received.map((action) => (action as { type: string }).type)).toEqual([
      nexusActions.createConversationSuccess.type,
      summarizerActions.uploadDocumentSuccess.type
    ]);
    expect(api.uploadConversationDocument).toHaveBeenCalledWith("nova", FILE);
  });

  it("turns API codes into messages", () => {
    const api = {
      uploadConversationDocument: vi.fn(() =>
        throwError(() => ({ error: { code: "summary_daily_limit" } }))
      )
    } as unknown as NexusApiService;
    const actions = new Subject<unknown>();
    const received = collect(uploadSummaryDocumentEffect(actions as unknown as Actions, api));
    actions.next(summarizerActions.uploadDocument({ conversationId: "c1", assistantId: "sys", file: FILE }));
    expect((received[0] as { error: string }).error).toContain("limite");
  });

  it("treats 404 as a conversation without document", () => {
    const api = {
      getConversationDocument: vi.fn(() => throwError(() => new HttpErrorResponse({ status: 404 })))
    } as unknown as NexusApiService;
    const store = { select: () => of({}) } as unknown as Store;
    const actions = new Subject<unknown>();
    const received = collect(loadSummaryDocumentEffect(actions as unknown as Actions, api, store));
    actions.next(summarizerActions.loadDocument({ conversationId: "c1" }));
    expect(received).toEqual([
      summarizerActions.loadDocumentSuccess({ conversationId: "c1", document: null, previousStage: null })
    ]);
  });

  it("polls every 3 s until a final stage (D36)", () => {
    const actions = new Subject<unknown>();
    const received = collect(pollSummaryDocumentEffect(actions as unknown as Actions));
    actions.next(summarizerActions.uploadDocumentSuccess({ document: doc({ stage: "resumindo" }) }));
    vi.advanceTimersByTime(SUMMARY_POLL_INTERVAL_MS);
    expect(received).toEqual([summarizerActions.loadDocument({ conversationId: "c1" })]);
    actions.next(
      summarizerActions.loadDocumentSuccess({
        conversationId: "c1",
        document: doc({ stage: "pronto" }),
        previousStage: "resumindo"
      })
    );
    vi.advanceTimersByTime(SUMMARY_POLL_INTERVAL_MS * 2);
    expect(received).toHaveLength(1);
  });

  it("reloads the messages once when the summary becomes ready (D31)", () => {
    const actions = new Subject<unknown>();
    const received = collect(reloadMessagesWhenSummaryReadyEffect(actions as unknown as Actions));
    const ready = (previousStage: string | null) =>
      summarizerActions.loadDocumentSuccess({
        conversationId: "c1",
        document: doc({ stage: "pronto" }),
        previousStage
      });
    actions.next(ready("resumindo"));
    actions.next(ready("pronto"));
    actions.next(ready(null));
    expect(received).toEqual([nexusActions.loadConversation({ conversationId: "c1" })]);
  });
});
