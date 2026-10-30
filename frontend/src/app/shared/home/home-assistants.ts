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
  /** SPEC-018 (RN-57): o resumidor, sempre primeiro e fora das vagas. */
  pinnedId?: string | null;
}

/** Rascunho do modal: marcados na ordem de marcacao (D7) e o padrao. */
export interface HomeDraft {
  selected: string[];
  defaultId: string | null;
  /** SPEC-018: o fixo nao entra em ``selected``, mas pode ser o padrao. */
  pinnedId?: string | null;
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
  const pinned =
    assistants.find((assistant) => assistant.id === home?.pinned_assistant_id) ??
    assistants.find((assistant) => assistant.is_system) ??
    null;
  if (pinned) {
    return withPinned(assistants, home, pinned);
  }
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
    return {
      assistants: ordered,
      defaultId,
      max,
      customized: home?.customized ?? false
    };
  }
  const first = assistants.slice(0, max);
  return {
    assistants: first,
    defaultId: first[0]?.id ?? null,
    max,
    customized: false
  };
}

/**
 * SPEC-018 (RN-57): o resumidor primeiro, fora das vagas. E o padrao de quem
 * nao personalizou e o recuo de quem perdeu o padrao gravado.
 */
function withPinned(
  assistants: readonly Assistant[],
  home: HomeAssistants | null,
  pinned: Assistant
): HomeCards {
  const max = home?.max ?? DEFAULT_HOME_ASSISTANTS_MAX;
  const others = assistants.filter((assistant) => assistant.id !== pinned.id);
  const byId = new Map(others.map((assistant) => [assistant.id, assistant]));
  const kept = (home?.assistant_ids ?? [])
    .filter((id) => id !== pinned.id)
    .map((id) => byId.get(id))
    .filter((assistant): assistant is Assistant => assistant !== undefined);
  if (home && (kept.length > 0 || home.customized)) {
    const wanted = home.default_assistant_id;
    const defaultId =
      wanted && (wanted === pinned.id || kept.some((assistant) => assistant.id === wanted))
        ? wanted
        : pinned.id;
    return {
      assistants: [pinned, ...kept],
      defaultId,
      max,
      customized: home.customized,
      pinnedId: pinned.id
    };
  }
  return {
    assistants: [pinned, ...others.slice(0, max)],
    defaultId: pinned.id,
    max,
    customized: false,
    pinnedId: pinned.id
  };
}

export function draftFrom(cards: HomeCards): HomeDraft {
  return {
    selected: cards.assistants
      .map((assistant) => assistant.id)
      .filter((id) => id !== cards.pinnedId),
    defaultId: cards.defaultId,
    ...(cards.pinnedId ? { pinnedId: cards.pinnedId } : {})
  };
}

/** SPEC-018: o cartao fixo nao tem caixa de marcacao. */
export function isPinned(draft: HomeDraft, id: string): boolean {
  return !!draft.pinnedId && draft.pinnedId === id;
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
  if (isPinned(draft, id)) {
    return draft;
  }
  if (isSelected(draft, id)) {
    const selected = draft.selected.filter((item) => item !== id);
    const fallback = draft.pinnedId ?? selected[0] ?? null;
    const defaultId = draft.defaultId === id ? fallback : draft.defaultId;
    return { ...draft, selected, defaultId };
  }
  if (draft.selected.length >= max) {
    return draft;
  }
  return { ...draft, selected: [...draft.selected, id], defaultId: draft.defaultId ?? id };
}

/** O padrao so pode ser um dos marcados ou o fixo (SPEC-018). */
export function setDefault(draft: HomeDraft, id: string): HomeDraft {
  return isSelected(draft, id) || isPinned(draft, id) ? { ...draft, defaultId: id } : draft;
}

export function canSave(draft: HomeDraft, max: number): boolean {
  return (
    draft.selected.length >= 1 &&
    draft.selected.length <= max &&
    draft.defaultId !== null &&
    (isSelected(draft, draft.defaultId) || isPinned(draft, draft.defaultId))
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
