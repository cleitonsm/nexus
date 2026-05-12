export interface Assistant {
  id: string;
  name: string;
  description: string | null;
  initial_prompt: string | null;
  created_at: string;
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
}

export interface Conversation {
  id: string;
  assistant_id: string;
  name: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  created_at: string;
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
