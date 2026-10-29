import { MenuVisibility } from "../../core/auth/access";
import { describeApiError } from "../documents/document-lifecycle";
import { Assistant } from "../models/nexus.models";

/** SPEC-017 (RN-51, D3): os mesmos limites do dominio no backend. */
export const MAX_ASSISTANT_NAME = 80;
export const MAX_ASSISTANT_DESCRIPTION = 500;
export const MAX_ASSISTANT_PROMPT = 4000;

export type ProfileField = "name" | "description" | "initialPrompt";

export const PROFILE_LIMITS: Readonly<Record<ProfileField, number>> = {
  name: MAX_ASSISTANT_NAME,
  description: MAX_ASSISTANT_DESCRIPTION,
  initialPrompt: MAX_ASSISTANT_PROMPT
};

/** O que o formulario guarda: texto livre, sem normalizar. */
export interface AssistantProfileDraft {
  name: string;
  description: string;
  initialPrompt: string;
}

/** Corpo do ``PUT /assistants/{id}``. */
export interface AssistantProfileInput {
  name: string;
  description: string | null;
  initial_prompt: string | null;
}

const PROFILE_ERROR_MESSAGES: Readonly<Record<string, string>> = {
  assistant_name_required: "Informe o nome do assistente.",
  assistant_name_too_long: `O nome pode ter até ${MAX_ASSISTANT_NAME} caracteres.`,
  assistant_description_too_long: `A descrição pode ter até ${MAX_ASSISTANT_DESCRIPTION} caracteres.`,
  assistant_prompt_too_long: `O prompt pode ter até ${MAX_ASSISTANT_PROMPT} caracteres.`,
  assistant_not_found: "O assistente não existe mais. Ele pode ter sido excluído.",
  forbidden: "Você não tem permissão para editar este assistente."
};

/** D4: vazio ou so espacos vira ``null``. */
export function normalizeOptionalText(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

export function profileDraftFrom(assistant: Assistant): AssistantProfileDraft {
  return {
    name: assistant.name,
    description: assistant.description ?? "",
    initialPrompt: assistant.initial_prompt ?? ""
  };
}

export function profileInputFrom(draft: AssistantProfileDraft): AssistantProfileInput {
  return {
    name: draft.name.trim(),
    description: normalizeOptionalText(draft.description),
    initial_prompt: normalizeOptionalText(draft.initialPrompt)
  };
}

/** Tamanho que conta para o limite: sem os espacos das pontas, como no backend. */
export function profileFieldLength(draft: AssistantProfileDraft, field: ProfileField): number {
  return draft[field].trim().length;
}

export function profileErrors(draft: AssistantProfileDraft): string[] {
  const errors: string[] = [];
  if (!draft.name.trim()) {
    errors.push(PROFILE_ERROR_MESSAGES["assistant_name_required"]);
  } else if (profileFieldLength(draft, "name") > MAX_ASSISTANT_NAME) {
    errors.push(PROFILE_ERROR_MESSAGES["assistant_name_too_long"]);
  }
  if (profileFieldLength(draft, "description") > MAX_ASSISTANT_DESCRIPTION) {
    errors.push(PROFILE_ERROR_MESSAGES["assistant_description_too_long"]);
  }
  if (profileFieldLength(draft, "initialPrompt") > MAX_ASSISTANT_PROMPT) {
    errors.push(PROFILE_ERROR_MESSAGES["assistant_prompt_too_long"]);
  }
  return errors;
}

/** Ha diferenca real (depois de normalizar) entre o formulario e o gravado. */
export function profileChanged(draft: AssistantProfileDraft, assistant: Assistant): boolean {
  const input = profileInputFrom(draft);
  return (
    input.name !== assistant.name ||
    input.description !== normalizeOptionalText(assistant.description) ||
    input.initial_prompt !== normalizeOptionalText(assistant.initial_prompt)
  );
}

/** D8: nome repetido e permitido; o formulario so avisa. */
export function duplicateNameWarning(
  draft: AssistantProfileDraft,
  assistants: readonly Assistant[],
  selfId: string
): string | null {
  const name = draft.name.trim().toLocaleLowerCase("pt-BR");
  if (!name) {
    return null;
  }
  const clash = assistants.some(
    (assistant) =>
      assistant.id !== selfId && assistant.name.trim().toLocaleLowerCase("pt-BR") === name
  );
  return clash ? "Já existe outro assistente com este nome. Você pode salvar mesmo assim." : null;
}

/**
 * D1: administrador, ou curador do assistente. A API so devolve ``groups`` a
 * quem gerencia o assistente, entao grupos preenchidos identificam o curador
 * dele. A API continua sendo a guarda (RNF-23).
 */
export function canEditAssistantProfile(
  menu: MenuVisibility,
  assistant: Assistant | null | undefined
): boolean {
  if (!assistant) {
    return false;
  }
  return menu.manageAssistants || (menu.manageDocuments && (assistant.groups?.length ?? 0) > 0);
}

/** Erro da API em portugues, pelo ``code`` da RN-51 quando houver. */
export function describeProfileError(error: unknown): string {
  const body = (error as { error?: { code?: unknown; detail?: { code?: unknown } } } | null)
    ?.error;
  const code = body?.detail?.code ?? body?.code;
  if (typeof code === "string" && code in PROFILE_ERROR_MESSAGES) {
    return PROFILE_ERROR_MESSAGES[code];
  }
  return describeApiError(error);
}
