import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";

import {
  Assistant,
  ChatResponse,
  Conversation,
  ConversationDetail,
  IngestedDocument
} from "../../shared/models/nexus.models";

interface CreateAssistantPayload {
  name: string;
  description: string | null;
}

interface CreateConversationPayload {
  assistant_id: string;
}

interface ChatPayload {
  question: string;
  top_k: number;
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
    return this.http.post<IngestedDocument>(
      `${this.baseUrl}/assistants/${assistantId}/documents`,
      formData
    );
  }

  createConversation(payload: CreateConversationPayload): Observable<Conversation> {
    return this.http.post<Conversation>(`${this.baseUrl}/conversations`, payload);
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
}
