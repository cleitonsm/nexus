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
/** Ciclo de vida do documento (SPEC-005). */
export type DocumentStatus = "pendente" | "processando" | "indexado" | "falhou" | "substituido";

export interface DocumentAccess {
  id: string;
  assistant_id: string;
  source_name: string;
  created_at: string;
  chunk_count: number;
  groups: string[];
  status: DocumentStatus;
  version: number;
  failure_reason: string | null;
  size_bytes: number | null;
  replaces_document_id: string | null;
  content_hash: string;
  has_original: boolean;
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
  /** Falso quando o documento citado foi excluído ou substituído (RN-29). */
  document_available?: boolean;
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
