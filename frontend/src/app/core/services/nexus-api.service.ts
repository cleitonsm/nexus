import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";

import {
  ApiKeyTestResult,
  ApiKeyStatus,
  Assistant,
  ChatResponse,
  Conversation,
  ConversationDetail,
  IngestedDocument
} from "../../shared/models/nexus.models";

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

@Injectable({ providedIn: "root" })
export class NexusApiService {
  private readonly baseUrl = "/api";

  constructor(private readonly http: HttpClient) {}

  listAssistants(): Observable<Assistant[]> {
    return this.http.get<Assistant[]>(`${this.baseUrl}/assistants`);
  }

  createAssistant(payload: CreateAssistantPayload): Observable<Assistant> {
    return this.http.post<Assistant>(`${this.baseUrl}/assistants`, payload);
  }

  deleteAssistant(assistantId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/assistants/${assistantId}`);
  }

  uploadDocument(
    assistantId: string,
    file: File,
    metadata?: Record<string, string>
  ): Observable<IngestedDocument> {
    const formData = new FormData();
    formData.set("file", file, file.name);
    if (metadata && Object.keys(metadata).length > 0) {
      formData.set("metadata", JSON.stringify(metadata));
    }
    // #region agent log
    fetch("http://127.0.0.1:7657/ingest/1e04e285-e754-4529-87f1-5953edf93f4e", { method: "POST", headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "a1f259" }, body: JSON.stringify({ sessionId: "a1f259", runId: "pre-fix", hypothesisId: "H3", location: "frontend/src/app/core/services/nexus-api.service.ts:uploadDocument", message: "frontend starting document upload", data: { fileSizeBytes: file.size, fileType: file.type, hasMetadata: Boolean(metadata && Object.keys(metadata).length > 0), metadataKeysCount: metadata ? Object.keys(metadata).length : 0, url: `${this.baseUrl}/assistants/${assistantId}/documents` }, timestamp: Date.now() }) }).catch(() => {});
    // #endregion
    return this.http.post<IngestedDocument>(
      `${this.baseUrl}/assistants/${assistantId}/documents`,
      formData
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
