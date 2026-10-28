export interface Assistant {
  id: string;
  name: string;
  description: string | null;
  initial_prompt: string | null;
  created_at: string;
  /** Grupos vinculados (RF-42); vazio para quem nao gerencia o assistente. */
  groups?: string[];
}

/** SPEC-016: acesso rapido efetivo da tela inicial (RN-49). */
export interface HomeAssistants {
  assistant_ids: string[];
  default_assistant_id: string | null;
  max: number;
  customized: boolean;
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

export type ReindexStatus = "running" | "succeeded" | "failed";

export interface ReindexJob {
  id: string;
  assistant_id: string;
  status: ReindexStatus;
  target_collection: string;
  total_documents: number;
  processed_documents: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface SparseParameters {
  k1: number;
  b: number;
  average_length: number;
}

/** Estado do indice de busca de um assistente (RF-31, PC-D2). */
export interface IndexStatus {
  assistant_id: string;
  embedding_model: string;
  pipeline_version: string;
  collection_name: string | null;
  outdated: boolean;
  documents_total: number;
  documents_indexed: number;
  documents_without_original: string[];
  last_reindex: ReindexJob | null;
  sparse_parameters_changed: boolean;
  sparse_parameters_recorded: SparseParameters | null;
  sparse_parameters_current: SparseParameters | null;
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

/** Provedor do LLM (SPEC-013 D5); ``custom`` aceita URL digitada. */
export type LlmProvider = "openai" | "gemini" | "custom";

/** Modelo permitido na credencial; preco por 1K tokens opcional (D8). */
export interface LlmModel {
  name: string;
  input_per_1k: string | null;
  output_per_1k: string | null;
}

/** Credencial de LLM (SPEC-013). A chave nunca volta: so ``key_configured``. */
export interface LlmCredential {
  id: string;
  name: string;
  provider: LlmProvider;
  api_url: string;
  models: LlmModel[];
  default_model: string;
  is_default: boolean;
  key_configured: boolean;
  /** Assistentes que escolheram esta credencial. */
  assistant_ids: string[];
  /** So na padrao: assistentes que a seguem sem escolha propria. */
  following_assistant_ids: string[];
}

export interface LlmCredentialList {
  items: LlmCredential[];
  provider_urls: Record<string, string>;
  /** Moeda dos precos (LLM_PRICE_CURRENCY). */
  currency: string;
}

export interface LlmCredentialInput {
  name: string;
  provider: LlmProvider;
  api_url: string | null;
  models: LlmModel[];
  default_model: string;
  /** Obrigatoria ao criar e ao trocar provedor ou URL (D12); vazia mantem a gravada. */
  api_key: string | null;
  make_default?: boolean;
}

export interface LlmCredentialOption {
  id: string;
  name: string;
  provider: LlmProvider;
  models: string[];
  default_model: string;
  is_default: boolean;
}

/** D11: quem segue a padrao e quem recua ao modelo padrao dela. */
export interface DefaultChangeImpact {
  credential_id: string;
  following_assistant_ids: string[];
  falling_back_assistant_ids: string[];
}

export interface LlmCredentialTestResult {
  ok: boolean;
  credential_id: string;
  model: string;
  message: string;
  response_preview: string;
}

/** 409 da RN-38: quem usa a credencial ou os modelos. */
export interface LlmCredentialConflict {
  message: string;
  assistant_ids: string[];
  models: string[];
  is_default: boolean;
}

export type LlmSource = "assistant" | "default" | "environment";

export interface AssistantLlm {
  credential_id: string | null;
  model: string | null;
  effective_credential_id: string | null;
  effective_credential_name: string | null;
  effective_provider: LlmProvider;
  effective_model: string;
  source: LlmSource;
  model_falls_back: boolean;
}

export interface AssistantLlmInput {
  credential_id: string | null;
  model: string | null;
}

export type RetrievalOrigin = "assistant" | "default";

export interface RetrievalField<T> {
  stored: T | null;
  effective: T;
  origin: RetrievalOrigin;
}

export interface AssistantRetrieval {
  hybrid_enabled: RetrievalField<boolean>;
  candidates: RetrievalField<number>;
  top_k: RetrievalField<number>;
  min_score: RetrievalField<number>;
  top_k_clamped: boolean;
  /** Faixas aceitas (D6): [minimo, maximo]. */
  limits: {
    candidates: [number, number];
    top_k: [number, number];
    min_score: [number, number];
  };
}

/** Substitui o perfil inteiro; ``null`` volta ao padrao. */
export interface AssistantRetrievalInput {
  hybrid_enabled: boolean | null;
  candidates: number | null;
  top_k: number | null;
  min_score: number | null;
}

/** Evento da resposta em streaming (RF-58, SPEC-006). */
export type ChatStreamEvent =
  | { kind: "delta"; text: string }
  | { kind: "replace"; text: string }
  | { kind: "done"; response: ChatResponse }
  | { kind: "error"; status: number; detail: string };

/** Resposta em andamento no chat: pergunta ja exibida e texto parcial. */
export interface ChatStreamState {
  conversationId: string | null;
  question: string;
  text: string;
}

/** Avaliacao de uma resposta (RF-61, D8): util ou nao util. */
export type FeedbackRating = "util" | "nao_util";
export type FeedbackStatus = "nao_aplicavel" | "pendente" | "validado" | "descartado";

export interface MessageFeedback {
  id: string;
  message_id: string;
  conversation_id: string;
  assistant_id: string;
  rating: FeedbackRating;
  comment: string | null;
  status: FeedbackStatus;
  created_at: string;
  updated_at: string;
  /** So na visao do curador (RN-33). */
  question?: string | null;
  answer?: string | null;
  cited_documents?: string[];
  expected_answer?: string | null;
  source_documents?: string[];
  out_of_scope?: boolean;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
}

export interface FeedbackReview {
  decision: "validado" | "descartado";
  expected_answer?: string | null;
  source_documents?: string[];
  out_of_scope?: boolean;
}

/** Consumo por usuario ou por conversa (RF-57); custo e estimativa. */
export interface UsageSummary {
  key: string;
  questions: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  user_id: string | null;
  user_name: string | null;
  assistant_id: string | null;
  last_used_at: string | null;
}

export interface UsageReport {
  occurred_from: string;
  occurred_to: string;
  currency: string;
  model: string;
  estimated: boolean;
  by_user: UsageSummary[];
  by_conversation: UsageSummary[];
  total_questions: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_estimated_cost: number;
}

/** Limite de perguntas por usuario (D3); 0 desliga a janela. */
export interface UsageLimits {
  per_minute: number;
  per_day: number;
  /** "padrao" vem do ambiente; "configurado", da tela. */
  source?: "padrao" | "configurado";
}
