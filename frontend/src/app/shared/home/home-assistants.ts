/**
 * SPEC-016: regras puras do acesso rapido da tela inicial (RF-103 a RF-107).
 * O modal e a tela so apresentam; o que mostrar e o que pode ser salvo vem daqui.
 */

import { Assistant, HomeAssistants } from "../models/nexus.models";

/** D1: igual ao dominio; vale so enquanto a API ainda nao respondeu. */
export const DEFAULT_HOME_ASSISTANTS_MAX = 4;

export interface HomeCards {
  assistants: Assistant[];
  defaultId: string | null;
  max: number;
  customized: boolean;
}

/** Rascunho do modal: marcados na ordem de marcacao (D7) e o padrao. */
export interface HomeDraft {
  selected: string[];
  defaultId: string | null;
}

/**
 * Cartoes da tela inicial: o acesso rapido efetivo da API (RN-49), sem ids que a
 * lista de assistentes nao tem mais. Antes da resposta (ou se ela falhar), vale a
 * D4 sobre a lista local.
 */
export function resolveHomeCards(
  assistants: readonly Assistant[],
  home: HomeAssistants | null
): HomeCards {
  const byId = new Map(assistants.map((assistant) => [assistant.id, assistant]));
  const max = home?.max ?? DEFAULT_HOME_ASSISTANTS_MAX;
  const kept = (home?.assistant_ids ?? [])
    .map((id) => byId.get(id))
    .filter((assistant): assistant is Assistant => assistant !== undefined);
  if (kept.length > 0) {
    const defaultId =
      home?.default_assistant_id && byId.has(home.default_assistant_id) &&
      kept.some((assistant) => assistant.id === home.default_assistant_id)
        ? home.default_assistant_id
        : kept[0].id;
    const ordered = [
      ...kept.filter((assistant) => assistant.id === defaultId),
      ...kept.filter((assistant) => assistant.id !== defaultId)
    ];
    return { assistants: ordered, defaultId, max, customized: home?.customized ?? false };
  }
  const first = assistants.slice(0, max);
  return { assistants: first, defaultId: first[0]?.id ?? null, max, customized: false };
}

export function draftFrom(cards: HomeCards): HomeDraft {
  return { selected: cards.assistants.map((assistant) => assistant.id), defaultId: cards.defaultId };
}

export function isSelected(draft: HomeDraft, id: string): boolean {
  return draft.selected.includes(id);
}

/** RN-47: no limite, os nao marcados ficam desabilitados. */
export function isToggleDisabled(draft: HomeDraft, id: string, max: number): boolean {
  return !isSelected(draft, id) && draft.selected.length >= max;
}

/**
 * Marca ou desmarca. O primeiro marcado vira padrao; desmarcar o padrao passa o
 * papel ao primeiro que sobrou, para o padrao continuar entre os marcados.
 */
export function toggleAssistant(draft: HomeDraft, id: string, max: number): HomeDraft {
  if (isSelected(draft, id)) {
    const selected = draft.selected.filter((item) => item !== id);
    const defaultId = draft.defaultId === id ? (selected[0] ?? null) : draft.defaultId;
    return { selected, defaultId };
  }
  if (draft.selected.length >= max) {
    return draft;
  }
  return { selected: [...draft.selected, id], defaultId: draft.defaultId ?? id };
}

/** O padrao so pode ser um dos marcados. */
export function setDefault(draft: HomeDraft, id: string): HomeDraft {
  return isSelected(draft, id) ? { ...draft, defaultId: id } : draft;
}

export function canSave(draft: HomeDraft, max: number): boolean {
  return (
    draft.selected.length >= 1 &&
    draft.selected.length <= max &&
    draft.defaultId !== null &&
    isSelected(draft, draft.defaultId)
  );
}

/** RF-107: contador "n de N". */
export function counterLabel(draft: HomeDraft, max: number): string {
  return `${draft.selected.length} de ${max}`;
}

/**
 * D5: "Nova conversa" volta ao padrao; sem padrao conhecido, fica no ativo.
 */
export function newConversationAssistant(
  defaultId: string | null,
  activeId: string | null
): string | null {
  return defaultId ?? activeId;
}
