/**
 * Resposta em streaming (RF-58) e mensagens de erro do chat (RN-32).
 * Funcoes puras, sem Angular, para serem testadas com o Vitest.
 */
import { ChatResponse, ChatStreamEvent } from "../models/nexus.models";
import { UNEXPECTED_ERROR, describeApiError } from "../documents/document-lifecycle";

/**
 * Le o texto acumulado da resposta (``partialText`` do HttpClient) e devolve
 * so os eventos completos ainda nao entregues. Um evento termina numa linha
 * em branco; o resto fica para a proxima leitura.
 */
export class ServerSentEventsReader {
  private consumed = 0;

  read(accumulated: string): ChatStreamEvent[] {
    const pending = accumulated.slice(this.consumed);
    const lastBreak = pending.lastIndexOf("\n\n");
    if (lastBreak < 0) {
      return [];
    }
    this.consumed += lastBreak + 2;
    return pending
      .slice(0, lastBreak)
      .split("\n\n")
      .map(parseEventBlock)
      .filter((event): event is ChatStreamEvent => event !== null);
  }
}

export function parseEventBlock(block: string): ChatStreamEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) {
      continue;
    }
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    const value = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "event") {
      name = value;
    } else if (field === "data") {
      data.push(value);
    }
  }
  if (data.length === 0) {
    return null;
  }
  let payload: unknown;
  try {
    payload = JSON.parse(data.join("\n"));
  } catch {
    return null;
  }
  return toEvent(name, payload);
}

function toEvent(name: string, payload: unknown): ChatStreamEvent | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }
  const body = payload as Record<string, unknown>;
  switch (name) {
    case "delta":
    case "replace":
      return { kind: name, text: String(body["text"] ?? "") };
    case "done":
      return { kind: "done", response: payload as ChatResponse };
    case "error":
      return {
        kind: "error",
        status: Number(body["status"] ?? 500),
        detail: String(body["detail"] ?? UNEXPECTED_ERROR)
      };
    default:
      return null;
  }
}

/** Corpo de erro da API (429 do limite de uso, RN-32). */
interface UsageLimitBody {
  code: "usage_limit";
  window: "minute" | "day" | string;
  limit: number;
  retry_at: string;
}

/**
 * Mensagem de erro do chat. Com ``responseType: "text"`` o corpo chega como
 * texto; por isso ele e lido como JSON antes de virar mensagem.
 */
export function describeChatError(error: unknown, now: Date = new Date()): string {
  const body = errorBody(error);
  if (isUsageLimit(body)) {
    return describeUsageLimit(body, now);
  }
  if (body !== undefined) {
    return describeApiError({ error: body });
  }
  return describeApiError(error);
}

export function describeUsageLimit(body: UsageLimitBody, now: Date = new Date()): string {
  const window = body.window === "day" ? "por dia" : "por minuto";
  const retryAt = new Date(body.retry_at);
  const when = Number.isNaN(retryAt.getTime()) ? "mais tarde" : formatRetry(retryAt, now);
  return `Você atingiu o limite de ${body.limit} perguntas ${window}. Poderá perguntar novamente ${when}.`;
}

function formatRetry(retryAt: Date, now: Date): string {
  const time = retryAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const sameDay = retryAt.toDateString() === now.toDateString();
  if (sameDay) {
    return `às ${time}`;
  }
  const date = retryAt.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  return `em ${date}, às ${time}`;
}

function errorBody(error: unknown): unknown {
  if (typeof error !== "object" || error === null || !("error" in error)) {
    return undefined;
  }
  const body = (error as { error?: unknown }).error;
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch {
      return { detail: body };
    }
  }
  return body;
}

function isUsageLimit(body: unknown): body is UsageLimitBody {
  return (
    typeof body === "object" &&
    body !== null &&
    (body as { code?: unknown }).code === "usage_limit"
  );
}
