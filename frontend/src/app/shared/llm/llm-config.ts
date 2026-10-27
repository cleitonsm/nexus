/**
 * Regras de tela da SPEC-013 (credenciais de LLM e configuracao do assistente),
 * sem Angular, para serem testadas isoladamente. A API repete toda validacao.
 */
import {
  AssistantRetrieval,
  AssistantRetrievalInput,
  LlmCredential,
  LlmCredentialConflict,
  LlmModel,
  LlmProvider,
  LlmSource
} from "../models/nexus.models";

export const LLM_PROVIDERS: { value: LlmProvider; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini (Google)" },
  { value: "custom", label: "Personalizado (compatível com OpenAI)" }
];

export function providerLabel(provider: LlmProvider): string {
  return LLM_PROVIDERS.find((item) => item.value === provider)?.label ?? provider;
}

/** RN-40: de onde vem o LLM que o assistente usa. */
export function llmSourceLabel(source: LlmSource): string {
  switch (source) {
    case "assistant":
      return "credencial escolhida para este assistente";
    case "default":
      return "credencial padrão do sistema";
    default:
      return "ambiente (.env), sem credencial cadastrada";
  }
}

/** URL que vale: a do provedor nos presets (D5); a digitada no personalizado. */
export function effectiveUrl(
  provider: LlmProvider,
  apiUrl: string,
  providerUrls: Record<string, string>
): string {
  return provider === "custom" ? apiUrl.trim() : providerUrls[provider] ?? "";
}

/** D12: trocar o destino exige chave nova. */
export function destinationChanged(
  current: LlmCredential,
  provider: LlmProvider,
  apiUrl: string,
  providerUrls: Record<string, string>
): boolean {
  return (
    current.provider !== provider ||
    current.api_url !== effectiveUrl(provider, apiUrl, providerUrls)
  );
}

export interface ModelRow {
  name: string;
  inputPrice: string;
  outputPrice: string;
}

/** D4/D8: nomes sem espaco nem repeticao; preco de entrada e saida juntos, nao negativos. */
export function modelsFromRows(rows: ModelRow[]): { models: LlmModel[]; errors: string[] } {
  const errors: string[] = [];
  const models: LlmModel[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const name = row.name.trim();
    if (!name) {
      continue;
    }
    if (/\s/.test(name)) {
      errors.push(`O modelo "${name}" não pode ter espaços.`);
      continue;
    }
    if (seen.has(name)) {
      errors.push(`O modelo "${name}" está repetido.`);
      continue;
    }
    seen.add(name);
    const input = normalizePrice(row.inputPrice);
    const output = normalizePrice(row.outputPrice);
    if (input === undefined || output === undefined) {
      errors.push(`Preço inválido no modelo "${name}".`);
      continue;
    }
    if ((input === null) !== (output === null)) {
      errors.push(`Informe os dois preços do modelo "${name}", ou nenhum.`);
      continue;
    }
    models.push({ name, input_per_1k: input, output_per_1k: output });
  }
  if (models.length === 0 && errors.length === 0) {
    errors.push("Informe ao menos um modelo.");
  }
  return { models, errors };
}

/** ``null``: vazio; ``undefined``: invalido. Aceita virgula decimal. */
function normalizePrice(raw: string): string | null | undefined {
  const value = raw.trim().replace(",", ".");
  if (!value) {
    return null;
  }
  if (!/^\d+(\.\d+)?$/.test(value)) {
    return undefined;
  }
  return value;
}

export function priceLabel(model: LlmModel, currency: string): string {
  if (model.input_per_1k === null || model.output_per_1k === null) {
    return "sem preço (usa o do ambiente)";
  }
  return `${currency} ${model.input_per_1k} entrada / ${model.output_per_1k} saída por 1K tokens`;
}

/** O 409 da RN-38, quando a resposta for dele. */
export function parseConflict(error: unknown): LlmCredentialConflict | null {
  if (typeof error !== "object" || error === null || !("error" in error)) {
    return null;
  }
  const detail = (error as { error?: { detail?: unknown } }).error?.detail;
  if (
    typeof detail !== "object" ||
    detail === null ||
    (detail as { code?: unknown }).code !== "llm_credential_in_use"
  ) {
    return null;
  }
  const value = detail as Partial<LlmCredentialConflict>;
  return {
    message: String(value.message ?? ""),
    assistant_ids: Array.isArray(value.assistant_ids) ? value.assistant_ids.map(String) : [],
    models: Array.isArray(value.models) ? value.models.map(String) : [],
    is_default: Boolean(value.is_default)
  };
}

export function describeConflict(
  conflict: LlmCredentialConflict,
  nameOf: (assistantId: string) => string
): string {
  const names = conflict.assistant_ids.map(nameOf);
  const list = names.length ? ` Assistentes afetados: ${names.join(", ")}.` : "";
  if (conflict.models.length) {
    return (
      `Os modelos ${conflict.models.join(", ")} estão em uso e não podem sair da lista.` + list
    );
  }
  if (conflict.is_default) {
    return "A credencial padrão não pode ser excluída. Torne outra padrão antes." + list;
  }
  return "A credencial está em uso e não pode ser excluída." + list;
}

export interface RetrievalDraft {
  hybrid: "" | "on" | "off";
  candidates: string;
  topK: string;
  minScore: string;
}

export function retrievalDraftFrom(retrieval: AssistantRetrieval): RetrievalDraft {
  const stored = retrieval.hybrid_enabled.stored;
  return {
    hybrid: stored === null ? "" : stored ? "on" : "off",
    candidates: textOf(retrieval.candidates.stored),
    topK: textOf(retrieval.top_k.stored),
    minScore: textOf(retrieval.min_score.stored)
  };
}

function textOf(value: number | null): string {
  return value === null ? "" : String(value);
}

/**
 * Converte o rascunho no corpo da API (campo vazio = padrao) e confere as faixas
 * da D6 e a T3 (top_k efetivo <= candidatos efetivos), como a API fara.
 */
export function retrievalInputFrom(
  draft: RetrievalDraft,
  current: AssistantRetrieval
): { input: AssistantRetrievalInput; errors: string[] } {
  const errors: string[] = [];
  const candidates = integerOf(draft.candidates, "Candidatos", current.limits.candidates, errors);
  const topK = integerOf(draft.topK, "Top k", current.limits.top_k, errors);
  const minScore = scoreOf(draft.minScore, current.limits.min_score, errors);
  const input: AssistantRetrievalInput = {
    hybrid_enabled: draft.hybrid === "" ? null : draft.hybrid === "on",
    candidates,
    top_k: topK,
    min_score: minScore
  };
  if (candidates !== null || topK !== null) {
    // Campo vazio vale o padrao do ambiente, que so e conhecido quando nada
    // esta gravado nele; senao, a API confere (T3).
    const effectiveCandidates = candidates ?? knownDefault(current.candidates);
    const effectiveTopK = topK ?? knownDefault(current.top_k);
    if (
      effectiveCandidates !== null &&
      effectiveTopK !== null &&
      effectiveTopK > effectiveCandidates
    ) {
      errors.push(
        `Top k (${effectiveTopK}) não pode passar dos candidatos (${effectiveCandidates}).`
      );
    }
  }
  return { input, errors };
}

function knownDefault(field: RetrievalFieldLike): number | null {
  return field.origin === "default" ? field.effective : null;
}

interface RetrievalFieldLike {
  effective: number;
  origin: string;
}

function integerOf(
  raw: string,
  label: string,
  [minimum, maximum]: [number, number],
  errors: string[]
): number | null {
  const value = raw.trim();
  if (!value) {
    return null;
  }
  if (!/^\d+$/.test(value)) {
    errors.push(`${label} deve ser um número inteiro.`);
    return null;
  }
  const parsed = Number(value);
  if (parsed < minimum || parsed > maximum) {
    errors.push(`${label} deve ficar entre ${minimum} e ${maximum}.`);
    return null;
  }
  return parsed;
}

function scoreOf(raw: string, [minimum, maximum]: [number, number], errors: string[]): number | null {
  const value = raw.trim().replace(",", ".");
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (!/^\d+(\.\d+)?$/.test(value) || Number.isNaN(parsed)) {
    errors.push("A nota mínima deve ser um número.");
    return null;
  }
  if (parsed < minimum || parsed > maximum) {
    errors.push(`A nota mínima deve ficar entre ${minimum} e ${maximum}.`);
    return null;
  }
  return parsed;
}

export const EMPTY_RETRIEVAL_INPUT: AssistantRetrievalInput = {
  hybrid_enabled: null,
  candidates: null,
  top_k: null,
  min_score: null
};
