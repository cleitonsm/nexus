import { Injectable } from "@angular/core";
import { HttpClient, HttpEventType, HttpParams } from "@angular/common/http";
import { Observable, filter, mergeMap } from "rxjs";

import {
  ApiKeyTestResult,
  ApiKeyStatus,
  Assistant,
  AuditEvent,
  AuditFilters,
  ChatResponse,
  ChatStreamEvent,
  Conversation,
  ConversationDetail,
  DocumentAccess,
  FeedbackRating,
  FeedbackReview,
  MessageFeedback,
  UsageLimits,
  UsageReport
} from "../../shared/models/nexus.models";
import { ServerSentEventsReader } from "../../shared/chat/chat-stream";
import { SessionUser } from "../auth/auth.models";

interface CreateAssistantPayload {
  name: string;
  description: string | null;
  initial_prompt: string | null;
}

interface CreateConversationPayload {
  assistant_id: string;
}

interface ChatPayload {
  question: string;
  top_k: number;
}

interface SaveApiKeyPayload {
  api_key: string;
}

interface InferAssistantPayload {
  question: string;
}

@Injectable({ providedIn: "root" })
export class NexusApiService {
  private readonly baseUrl = "/api";

  constructor(private readonly http: HttpClient) {}

  getMe(): Observable<SessionUser> {
    return this.http.get<SessionUser>(`${this.baseUrl}/me`);
  }

  setAssistantGroups(assistantId: string, groups: string[]): Observable<{ groups: string[] }> {
    return this.http.put<{ groups: string[] }>(
      `${this.baseUrl}/assistants/${assistantId}/groups`,
      { groups }
    );
  }

  listDocuments(assistantId: string): Observable<DocumentAccess[]> {
    return this.http.get<DocumentAccess[]>(
      `${this.baseUrl}/assistants/${assistantId}/documents`
    );
  }

  setDocumentGroups(documentId: string, groups: string[]): Observable<DocumentAccess> {
    return this.http.put<DocumentAccess>(`${this.baseUrl}/documents/${documentId}/groups`, {
      groups
    });
  }

  listAuditEvents(filters: AuditFilters): Observable<AuditEvent[]> {
    return this.http.get<AuditEvent[]>(`${this.baseUrl}/admin/audit-events`, {
      params: auditParams(filters)
    });
  }

  listAssistants(): Observable<Assistant[]> {
    return this.http.get<Assistant[]>(`${this.baseUrl}/assistants`);
  }

  inferAssistant(question: string): Observable<{ assistant_id: string | null }> {
    const payload: InferAssistantPayload = { question };
    return this.http.post<{ assistant_id: string | null }>(
      `${this.baseUrl}/assistants/infer`,
      payload
    );
  }

  createAssistant(payload: CreateAssistantPayload): Observable<Assistant> {
    return this.http.post<Assistant>(`${this.baseUrl}/assistants`, payload);
  }

  deleteAssistant(assistantId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/assistants/${assistantId}`);
  }

  /** RF-48: a API responde 202 com o documento pendente; o worker o indexa. */
  uploadDocument(
    assistantId: string,
    file: File,
    metadata?: Record<string, string>,
    groups: string[] = []
  ): Observable<DocumentAccess> {
    const formData = new FormData();
    formData.set("file", file, file.name);
    if (metadata && Object.keys(metadata).length > 0) {
      formData.set("metadata", JSON.stringify(metadata));
    }
    // Restricao ja no envio (D8 da SPEC-004): os trechos nascem restritos.
    if (groups.length > 0) {
      formData.set("groups", JSON.stringify(groups));
    }
    return this.http.post<DocumentAccess>(
      `${this.baseUrl}/assistants/${assistantId}/documents`,
      formData
    );
  }

  getDocument(documentId: string): Observable<DocumentAccess> {
    return this.http.get<DocumentAccess>(`${this.baseUrl}/documents/${documentId}`);
  }

  deleteDocument(documentId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/documents/${documentId}`);
  }

  /** RF-51: nova versao; a atual continua respondendo ate a nova ser indexada. */
  replaceDocument(documentId: string, file: File): Observable<DocumentAccess> {
    const formData = new FormData();
    formData.set("file", file, file.name);
    return this.http.put<DocumentAccess>(
      `${this.baseUrl}/documents/${documentId}/content`,
      formData
    );
  }

  /** RF-54: reprocessa a partir do original guardado, sem novo envio. */
  reprocessDocument(documentId: string): Observable<DocumentAccess> {
    return this.http.post<DocumentAccess>(
      `${this.baseUrl}/documents/${documentId}/reprocess`,
      {}
    );
  }

  createConversation(payload: CreateConversationPayload): Observable<Conversation> {
    return this.http.post<Conversation>(`${this.baseUrl}/conversations`, payload);
  }

  deleteConversation(conversationId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/conversations/${conversationId}`);
  }

  getConversation(conversationId: string): Observable<ConversationDetail> {
    return this.http.get<ConversationDetail>(
      `${this.baseUrl}/conversations/${conversationId}`
    );
  }

  listAssistantConversations(assistantId: string): Observable<Conversation[]> {
    return this.http.get<Conversation[]>(
      `${this.baseUrl}/assistants/${assistantId}/conversations`
    );
  }

  sendChatMessage(conversationId: string, payload: ChatPayload): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(
      `${this.baseUrl}/conversations/${conversationId}/chat`,
      payload
    );
  }

  /**
   * RF-58: Server-Sent Events lidos pelo progresso do HttpClient, para que o
   * interceptor de autenticacao continue valendo. Cada leitura entrega so os
   * eventos completos ainda nao vistos.
   */
  streamChatMessage(conversationId: string, payload: ChatPayload): Observable<ChatStreamEvent> {
    const reader = new ServerSentEventsReader();
    return this.http
      .post(`${this.baseUrl}/conversations/${conversationId}/chat/stream`, payload, {
        observe: "events",
        reportProgress: true,
        responseType: "text",
        headers: { Accept: "text/event-stream" }
      })
      .pipe(
        filter(
          (event) =>
            event.type === HttpEventType.DownloadProgress ||
            event.type === HttpEventType.Response
        ),
        mergeMap((event) => {
          const text =
            event.type === HttpEventType.Response
              ? event.body ?? ""
              : (event as { partialText?: string }).partialText ?? "";
          return reader.read(text);
        })
      );
  }

  /** RF-61: so quem fez a pergunta avalia; a ultima avaliacao vale. */
  submitFeedback(
    messageId: string,
    rating: FeedbackRating,
    comment: string | null
  ): Observable<MessageFeedback> {
    return this.http.post<MessageFeedback>(`${this.baseUrl}/messages/${messageId}/feedback`, {
      rating,
      comment
    });
  }

  /** RN-33: avaliacoes negativas para o curador. */
  listFeedback(status: string, assistantId: string | null): Observable<MessageFeedback[]> {
    let params = new HttpParams().set("status", status);
    if (assistantId) {
      params = params.set("assistant_id", assistantId);
    }
    return this.http.get<MessageFeedback[]>(`${this.baseUrl}/feedback`, { params });
  }

  reviewFeedback(feedbackId: string, review: FeedbackReview): Observable<MessageFeedback> {
    return this.http.post<MessageFeedback>(
      `${this.baseUrl}/feedback/${feedbackId}/review`,
      review
    );
  }

  /** Itens validados no formato JSONL do conjunto de referencia (SPEC-001). */
  exportFeedback(assistantId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/feedback/export`, {
      params: new HttpParams().set("assistant_id", assistantId),
      responseType: "blob"
    });
  }

  getUsageReport(from: string | null, to: string | null): Observable<UsageReport> {
    let params = new HttpParams();
    if (from) {
      params = params.set("from", from);
    }
    if (to) {
      params = params.set("to", to);
    }
    return this.http.get<UsageReport>(`${this.baseUrl}/admin/usage`, { params });
  }

  getUsageLimits(): Observable<UsageLimits> {
    return this.http.get<UsageLimits>(`${this.baseUrl}/admin/usage-limits`);
  }

  saveUsageLimits(limits: UsageLimits): Observable<UsageLimits> {
    return this.http.put<UsageLimits>(`${this.baseUrl}/admin/usage-limits`, {
      per_minute: limits.per_minute,
      per_day: limits.per_day
    });
  }

  getApiKeyStatus(): Observable<ApiKeyStatus> {
    return this.http.get<ApiKeyStatus>(`${this.baseUrl}/admin/api-key/status`);
  }

  saveApiKey(payload: SaveApiKeyPayload): Observable<ApiKeyStatus> {
    return this.http.post<ApiKeyStatus>(`${this.baseUrl}/admin/api-key`, payload);
  }

  testApiKey(): Observable<ApiKeyTestResult> {
    return this.http.post<ApiKeyTestResult>(`${this.baseUrl}/admin/api-key/test`, {});
  }
}

/** So os filtros preenchidos viram parametros; as datas vao em ISO 8601. */
function auditParams(filters: AuditFilters): HttpParams {
  const entries: Record<string, string> = {
    user_id: filters.userId.trim(),
    action: filters.action.trim(),
    assistant_id: filters.assistantId.trim(),
    from: toIso(filters.from),
    to: toIso(filters.to)
  };
  let params = new HttpParams();
  for (const [name, value] of Object.entries(entries)) {
    if (value) {
      params = params.set(name, value);
    }
  }
  return params;
}

function toIso(localDateTime: string): string {
  if (!localDateTime.trim()) {
    return "";
  }
  const parsed = new Date(localDateTime);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString();
}
