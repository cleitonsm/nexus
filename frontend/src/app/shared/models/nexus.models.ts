export interface Assistant {
  id: string;
  name: string;
  description: string | null;
  initial_prompt: string | null;
  created_at: string;
  /** Grupos vinculados (RF-42); vazio para quem nao gerencia o assistente. */
  groups?: string[];
}

/** Documento de um assistente e os grupos a que esta restrito (RF-43). */
export interface DocumentAccess {
  id: string;
  assistant_id: string;
  source_name: string;
  created_at: string;
  chunk_count: number;
  groups: string[];
}

export interface AuditEvent {
  id: string;
  occurred_at: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
}

/** Filtros da consulta de auditoria (UC-13); texto vazio nao filtra. */
export interface AuditFilters {
  userId: string;
  action: string;
  assistantId: string;
  from: string;
  to: string;
}

export interface IngestedDocument {
  id: string;
  assistant_id: string;
  source_name: string;
  content_hash: string;
  created_at: string;
  collection_name: string;
  chunk_count: number;
  embedding_dimension: number;
  groups?: string[];
}

export interface Conversation {
  id: string;
  assistant_id: string;
  name: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Citation {
  number: number;
  document_id: string;
  chunk_id: string;
  source_name: string;
  section_path: string;
  page: number | null;
  score: number;
  excerpt: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  created_at: string;
  citations?: Citation[];
}

export interface ConversationDetail {
  id: string;
  assistant_id: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface ChatResponse {
  conversation_id: string;
  assistant_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  used_context_chunks: number;
  fallback_used: boolean;
  citations: Citation[];
  rewritten_query: string;
}

export interface ApiKeyStatus {
  configured: boolean;
}

export interface ApiKeyTestResult {
  ok: boolean;
  model: string;
  message: string;
  response_preview: string;
}
