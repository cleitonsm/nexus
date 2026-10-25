/**
 * FE-02: effects com os colaboradores simulados.
 *
 * Os effects funcionais recebem ``Actions``, a API e o ``Store`` como
 * parametros, entao rodam sem TestBed. Os timers usam o relogio falso do Vitest.
 */
import { Actions } from "@ngrx/effects";
import { Router } from "@angular/router";
import { Store } from "@ngrx/store";
import { Observable, Subject, of, throwError } from "rxjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NexusApiService } from "../core/services/nexus-api.service";
import { DOCUMENT_POLL_INTERVAL_MS } from "../shared/documents/document-lifecycle";
import {
  ChatResponse,
  ChatStreamEvent,
  Conversation,
  DocumentAccess
} from "../shared/models/nexus.models";
import { INTERRUPTED_ANSWER } from "./chat-stream-flow";
import { nexusActions } from "./nexus.actions";
import {
  navigateToChatEffect,
  pollDocumentStatusEffect,
  refreshDocumentAccessEffect,
  sendChatQuestionEffect,
  submitFeedbackEffect,
  uploadDocumentEffect
} from "./nexus.effects";

function documentAccess(overrides: Partial<DocumentAccess> = {}): DocumentAccess {
  return {
    id: "d1",
    assistant_id: "a1",
    source_name: "ferias.md",
    created_at: "2026-10-14T10:00:00Z",
    chunk_count: 0,
    groups: [],
    status: "pendente",
    version: 1,
    failure_reason: null,
    size_bytes: 10,
    replaces_document_id: null,
    content_hash: "h",
    has_original: true,
    ...overrides
  };
}

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

function storeWithActive(assistantId: string | null): Store {
  const nexus = { activeAssistantId: assistantId };
  return {
    select: (selector: (state: unknown) => unknown) => of(selector({ nexus }))
  } as unknown as Store;
}

describe("uploadDocumentEffect (C16)", () => {
  it("envia todos os arquivos selecionados, sem cancelar os anteriores", () => {
    const stream = new Subject<unknown>();
    const subjects = new Map<string, Subject<DocumentAccess>>();
    const upload = vi.fn((_assistant: string, file: File) => {
      const subject = new Subject<DocumentAccess>();
      subjects.set(file.name, subject);
      return subject.asObservable();
    });
    const received = collect(uploadDocumentEffect(actionsOf(stream), api({ uploadDocument: upload })));

    for (const name of ["a.md", "b.md", "c.md"]) {
      stream.next(
        nexusActions.uploadDocument({ assistantId: "a1", file: new File(["x"], name), metadata: {} })
      );
    }
    expect(upload).toHaveBeenCalledTimes(3);

    subjects.get("c.md")!.next(documentAccess({ id: "c" }));
    subjects.get("a.md")!.next(documentAccess({ id: "a" }));
    subjects.get("b.md")!.next(documentAccess({ id: "b" }));
    expect(received.map((action) => (action as { document: DocumentAccess }).document.id)).toEqual([
      "c",
      "a",
      "b"
    ]);
  });

  it("trata 409 de arquivo duplicado como falha com mensagem legivel, sem afetar os outros", () => {
    const stream = new Subject<unknown>();
    const duplicate = {
      error: { detail: { code: "duplicate_document", source_name: "ferias.md" } },
      status: 409
    };
    const upload = vi.fn((_assistant: string, file: File) =>
      file.name === "dup.md" ? throwError(() => duplicate) : of(documentAccess({ id: file.name }))
    );
    const received = collect(uploadDocumentEffect(actionsOf(stream), api({ uploadDocument: upload })));

    stream.next(
      nexusActions.uploadDocument({ assistantId: "a1", file: new File(["x"], "dup.md"), metadata: {} })
    );
    stream.next(
      nexusActions.uploadDocument({ assistantId: "a1", file: new File(["x"], "ok.md"), metadata: {} })
    );

    expect(received).toHaveLength(2);
    expect(received[0].type).toBe(nexusActions.uploadDocumentFailure.type);
    expect((received[0] as { error: string }).error).toContain("já foi enviado");
    expect(received[1].type).toBe(nexusActions.uploadDocumentSuccess.type);
  });

  it("repassa os grupos informados e usa lista vazia quando nao ha", () => {
    const stream = new Subject<unknown>();
    const upload = vi.fn(() => of(documentAccess()));
    collect(uploadDocumentEffect(actionsOf(stream), api({ uploadDocument: upload })));
    const file = new File(["x"], "a.md");

    stream.next(nexusActions.uploadDocument({ assistantId: "a1", file, metadata: {}, groups: ["rh"] }));
    stream.next(nexusActions.uploadDocument({ assistantId: "a1", file, metadata: {} }));

    expect(upload.mock.calls[0][3]).toEqual(["rh"]);
    expect(upload.mock.calls[1][3]).toEqual([]);
  });
});

describe("refreshDocumentAccessEffect", () => {
  it("recarrega a lista do assistente do documento enviado", () => {
    const stream = new Subject<unknown>();
    const received = collect(refreshDocumentAccessEffect(actionsOf(stream)));
    stream.next(nexusActions.uploadDocumentSuccess({ document: documentAccess({ assistant_id: "a9" }) }));
    expect(received).toEqual([nexusActions.loadDocumentAccess({ assistantId: "a9" })]);
  });
});

describe("pollDocumentStatusEffect (D4, RNF-33)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const inProgress = documentAccess({ status: "processando" });
  const done = documentAccess({ status: "indexado" });

  it("consulta de novo a cada 3 s enquanto houver documento em andamento", () => {
    const stream = new Subject<unknown>();
    const received = collect(pollDocumentStatusEffect(actionsOf(stream), storeWithActive("a1")));

    stream.next(nexusActions.loadDocumentAccessSuccess({ assistantId: "a1", documents: [inProgress] }));
    vi.advanceTimersByTime(DOCUMENT_POLL_INTERVAL_MS - 1);
    expect(received).toHaveLength(0);
    vi.advanceTimersByTime(1);
    expect(received).toEqual([nexusActions.loadDocumentAccess({ assistantId: "a1", background: true })]);
  });

  it("nao consulta quando tudo terminou", () => {
    const stream = new Subject<unknown>();
    const received = collect(pollDocumentStatusEffect(actionsOf(stream), storeWithActive("a1")));
    stream.next(nexusActions.loadDocumentAccessSuccess({ assistantId: "a1", documents: [done] }));
    vi.advanceTimersByTime(DOCUMENT_POLL_INTERVAL_MS * 3);
    expect(received).toHaveLength(0);
  });

  it("para ao sair da tela (stopDocumentPolling)", () => {
    const stream = new Subject<unknown>();
    const received = collect(pollDocumentStatusEffect(actionsOf(stream), storeWithActive("a1")));
    stream.next(nexusActions.loadDocumentAccessSuccess({ assistantId: "a1", documents: [inProgress] }));
    vi.advanceTimersByTime(DOCUMENT_POLL_INTERVAL_MS - 100);
    stream.next(nexusActions.stopDocumentPolling());
    vi.advanceTimersByTime(DOCUMENT_POLL_INTERVAL_MS * 3);
    expect(received).toHaveLength(0);
  });

  it("nao consulta se outro assistente foi selecionado", () => {
    const stream = new Subject<unknown>();
    const received = collect(pollDocumentStatusEffect(actionsOf(stream), storeWithActive("outro")));
    stream.next(nexusActions.loadDocumentAccessSuccess({ assistantId: "a1", documents: [inProgress] }));
    vi.advanceTimersByTime(DOCUMENT_POLL_INTERVAL_MS * 2);
    expect(received).toHaveLength(0);
  });
});

describe("submitFeedbackEffect", () => {
  it("devolve sucesso com o feedback gravado", () => {
    const stream = new Subject<unknown>();
    const feedback = { id: "f1", message_id: "m1", rating: "util" };
    const received = collect(
      submitFeedbackEffect(actionsOf(stream), api({ submitFeedback: () => of(feedback) }))
    );
    stream.next(nexusActions.submitFeedback({ messageId: "m1", rating: "util", comment: null }));
    expect(received[0].type).toBe(nexusActions.submitFeedbackSuccess.type);
  });

  it("devolve a falha com o id da mensagem para a tela mostrar o erro no lugar certo", () => {
    const stream = new Subject<unknown>();
    const received = collect(
      submitFeedbackEffect(
        actionsOf(stream),
        api({ submitFeedback: () => throwError(() => ({ error: { detail: "Sem acesso." } })) })
      )
    );
    stream.next(nexusActions.submitFeedback({ messageId: "m7", rating: "nao_util", comment: "x" }));
    expect(received).toEqual([
      nexusActions.submitFeedbackFailure({ messageId: "m7", error: "Sem acesso." })
    ]);
  });
});

describe("sendChatQuestionEffect (RF-58, D13)", () => {
  const conversation: Conversation = {
    id: "c1",
    assistant_id: "a1",
    name: null,
    created_at: "2026-10-14T10:00:00Z",
    updated_at: "2026-10-14T10:00:00Z",
    message_count: 0
  };

  const response = {
    conversation_id: "c1",
    assistant_id: "a1",
    user_message: { id: "u", conversation_id: "c1", role: "user", content: "?", created_at: "" },
    assistant_message: { id: "m", conversation_id: "c1", role: "assistant", content: "ok [1]", created_at: "" },
    used_context_chunks: 1,
    fallback_used: false,
    citations: [],
    rewritten_query: ""
  } as ChatResponse;

  function send(events: Observable<ChatStreamEvent>, conversationId: string | null = "c1") {
    const stream = new Subject<unknown>();
    const received = collect(
      sendChatQuestionEffect(
        actionsOf(stream),
        api({
          streamChatMessage: () => events,
          createConversation: () => of(conversation)
        })
      )
    );
    stream.next(
      nexusActions.sendChatQuestion({ assistantId: "a1", conversationId, question: "?", topK: 5 })
    );
    return { received, stream };
  }

  it("mostra a pergunta, transmite os trechos e termina com a resposta", () => {
    const { received } = send(
      of<ChatStreamEvent>(
        { kind: "delta", text: "ok " },
        { kind: "delta", text: "[1]" },
        { kind: "done", response }
      )
    );
    expect(received.map((action) => action.type)).toEqual([
      nexusActions.chatStreamStarted.type,
      nexusActions.chatStreamDelta.type,
      nexusActions.chatStreamDelta.type,
      nexusActions.sendChatQuestionSuccess.type
    ]);
  });

  it("cria a conversa quando nao ha uma e a torna atual so com a resposta pronta", () => {
    const { received } = send(of<ChatStreamEvent>({ kind: "done", response }), null);
    const types = received.map((action) => action.type);
    expect(types.indexOf(nexusActions.createConversationSuccess.type)).toBeLessThan(
      types.indexOf(nexusActions.sendChatQuestionSuccess.type)
    );
  });

  it("evento de erro (429, por exemplo) vira falha com a mensagem da API", () => {
    const { received } = send(
      of<ChatStreamEvent>({ kind: "error", status: 429, detail: "Limite de uso atingido." })
    );
    expect(received.at(-1)).toEqual(nexusActions.sendChatQuestionFailure({ error: "Limite de uso atingido." }));
  });

  it("fim da conexao sem evento final recarrega a conversa e avisa o usuario", () => {
    const { received } = send(of<ChatStreamEvent>({ kind: "delta", text: "par" }));
    expect(received.slice(-2)).toEqual([
      nexusActions.sendChatQuestionFailure({ error: INTERRUPTED_ANSWER }),
      nexusActions.loadConversation({ conversationId: "c1" })
    ]);
  });

  it("parar a resposta cancela sem mostrar erro", () => {
    const events = new Subject<ChatStreamEvent>();
    const { received, stream } = send(events.asObservable());
    events.next({ kind: "delta", text: "par" });
    stream.next(nexusActions.cancelChatStream());
    expect(received.map((action) => action.type)).toContain(nexusActions.chatStreamCancelled.type);
    expect(received.map((action) => action.type)).not.toContain(
      nexusActions.sendChatQuestionFailure.type
    );
  });

  it("falha de rede vira mensagem de erro do chat", () => {
    const { received } = send(throwError(() => ({ error: { detail: "Sem conexão." } })));
    expect(received.at(-1)!.type).toBe(nexusActions.sendChatQuestionFailure.type);
  });
});

/** CT-80 (SPEC-010, RF-77): selecionar assistente, conversa ou nova conversa leva ao chat. */
describe("navigateToChatEffect", () => {
  function router(url: string) {
    const navigateByUrl = vi.fn(() => Promise.resolve(true));
    return { fake: { url, navigateByUrl } as unknown as Router, navigateByUrl };
  }

  const conversation = { id: "c1" } as Conversation;
  const triggers = [
    nexusActions.selectAssistant({ assistantId: "a1" }),
    nexusActions.selectConversation({ conversationId: "c1" }),
    nexusActions.createConversationSuccess({ assistantId: "a1", conversation })
  ];

  it.each(triggers.map((action) => [action.type, action]))(
    "navigates to /chat on %s from another screen",
    (_type, action) => {
      const actions = new Subject<unknown>();
      const { fake, navigateByUrl } = router("/admin/audit");
      collect(navigateToChatEffect(actionsOf(actions), fake));

      actions.next(action);

      expect(navigateByUrl).toHaveBeenCalledWith("/chat");
    }
  );

  it("does not navigate when the chat is already open", () => {
    const actions = new Subject<unknown>();
    const { fake, navigateByUrl } = router("/chat");
    collect(navigateToChatEffect(actionsOf(actions), fake));

    triggers.forEach((action) => actions.next(action));

    expect(navigateByUrl).not.toHaveBeenCalled();
  });

  it("ignores unrelated actions", () => {
    const actions = new Subject<unknown>();
    const { fake, navigateByUrl } = router("/feedback");
    collect(navigateToChatEffect(actionsOf(actions), fake));

    actions.next(nexusActions.loadAssistants());

    expect(navigateByUrl).not.toHaveBeenCalled();
  });
});
