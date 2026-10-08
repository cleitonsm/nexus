/** SPEC-006: leitura do streaming (RF-58) e mensagem do limite de uso (RN-32). */
import { describe, expect, it } from "vitest";

import { ServerSentEventsReader, describeChatError, parseEventBlock } from "./chat-stream";

const done = {
  conversation_id: "conv-1",
  assistant_id: "a-1",
  user_message: { id: "m-1", conversation_id: "conv-1", role: "user", content: "P", created_at: "" },
  assistant_message: {
    id: "m-2",
    conversation_id: "conv-1",
    role: "assistant",
    content: "Trinta dias [1].",
    created_at: ""
  },
  used_context_chunks: 1,
  fallback_used: false,
  citations: [],
  rewritten_query: "P"
};

describe("ServerSentEventsReader", () => {
  it("delivers only complete events, once, as the text accumulates", () => {
    const reader = new ServerSentEventsReader();
    const first = 'event: delta\ndata: {"text": "Trinta"}\n\nevent: delta\ndata: {"te';
    expect(reader.read(first)).toEqual([{ kind: "delta", text: "Trinta" }]);
    const second = first + 'xt": " dias"}\n\n';
    expect(reader.read(second)).toEqual([{ kind: "delta", text: " dias" }]);
    expect(reader.read(second)).toEqual([]);
    const third = second + `event: done\ndata: ${JSON.stringify(done)}\n\n`;
    const [event] = reader.read(third);
    expect(event.kind).toBe("done");
    expect(event.kind === "done" && event.response.assistant_message.content).toBe(
      "Trinta dias [1]."
    );
  });

  it("keeps accents and line breaks of the streamed text", () => {
    const reader = new ServerSentEventsReader();
    const events = reader.read('event: delta\ndata: {"text": "Férias\\nde 30 dias"}\n\n');
    expect(events).toEqual([{ kind: "delta", text: "Férias\nde 30 dias" }]);
  });

  it("reads replace and error events and ignores comments and unknown names", () => {
    expect(parseEventBlock('event: replace\ndata: {"text": "Nao encontrei"}')).toEqual({
      kind: "replace",
      text: "Nao encontrei"
    });
    expect(parseEventBlock('event: error\ndata: {"status": 502, "detail": "LLM fora"}')).toEqual({
      kind: "error",
      status: 502,
      detail: "LLM fora"
    });
    expect(parseEventBlock(": keep-alive")).toBeNull();
    expect(parseEventBlock('event: other\ndata: {"x": 1}')).toBeNull();
    expect(parseEventBlock("event: delta\ndata: {invalido")).toBeNull();
  });
});

describe("describeChatError", () => {
  const now = new Date(2026, 9, 8, 12, 0, 0);

  it("tells when the user can ask again after the minute limit", () => {
    const retryAt = new Date(2026, 9, 8, 12, 0, 42);
    const body = JSON.stringify({
      detail: "Limite de perguntas atingido.",
      code: "usage_limit",
      window: "minute",
      limit: 20,
      retry_at: retryAt.toISOString()
    });
    const message = describeChatError({ status: 429, error: body }, now);
    expect(message).toContain("limite de 20 perguntas por minuto");
    expect(message).toContain("às 12:00");
  });

  it("includes the date when the day limit frees on another day", () => {
    const retryAt = new Date(2026, 9, 9, 9, 30, 0);
    const message = describeChatError(
      {
        status: 429,
        error: { code: "usage_limit", window: "day", limit: 500, retry_at: retryAt.toISOString() }
      },
      now
    );
    expect(message).toContain("500 perguntas por dia");
    expect(message).toContain("09/10");
  });

  it("falls back to the API detail for other errors, as text or object", () => {
    expect(describeChatError({ status: 404, error: '{"detail": "conversation not found"}' })).toBe(
      "conversation not found"
    );
    expect(describeChatError({ status: 409, error: { detail: "index outdated" } })).toBe(
      "index outdated"
    );
    expect(describeChatError({ status: 502, error: "Bad Gateway" })).toBe("Bad Gateway");
  });
});
