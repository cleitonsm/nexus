import { describe, expect, it } from "vitest";

import { MenuVisibility } from "../../core/auth/access";
import { Assistant } from "../models/nexus.models";
import {
  MAX_ASSISTANT_DESCRIPTION,
  MAX_ASSISTANT_NAME,
  MAX_ASSISTANT_PROMPT,
  canEditAssistantProfile,
  describeProfileError,
  duplicateNameWarning,
  normalizeOptionalText,
  profileChanged,
  profileDraftFrom,
  profileErrors,
  profileInputFrom
} from "./assistant-profile";

const ASSISTANT: Assistant = {
  id: "juridico",
  name: "Assistente jurídico",
  description: "Contratos",
  initial_prompt: "Aja como advogado.",
  created_at: "2026-10-29T00:00:00Z",
  groups: ["juridico"]
};

const MENU: MenuVisibility = {
  manageAssistants: false,
  manageDocuments: false,
  configureLlm: false,
  viewAudit: false,
  viewUsage: false,
  reviewFeedback: false,
  viewArchived: false
};

describe("assistant-profile (CT-136, SPEC-017)", () => {
  it("usa os limites aprovados na D3", () => {
    expect([MAX_ASSISTANT_NAME, MAX_ASSISTANT_DESCRIPTION, MAX_ASSISTANT_PROMPT]).toEqual([
      80, 500, 4000
    ]);
  });

  it("normaliza vazio para null e apara espacos (D4)", () => {
    expect(normalizeOptionalText("   ")).toBeNull();
    expect(normalizeOptionalText(null)).toBeNull();
    expect(
      profileInputFrom({ name: "  Jurídico ", description: " ", initialPrompt: " p " })
    ).toEqual({ name: "Jurídico", description: null, initial_prompt: "p" });
  });

  it("valida nome obrigatorio e os limites", () => {
    const draft = profileDraftFrom(ASSISTANT);
    expect(profileErrors(draft)).toEqual([]);
    expect(profileErrors({ ...draft, name: "  " })).toHaveLength(1);
    expect(profileErrors({ ...draft, name: "n".repeat(81) })).toHaveLength(1);
    expect(profileErrors({ ...draft, description: "d".repeat(500) })).toEqual([]);
    expect(profileErrors({ ...draft, description: "d".repeat(501) })).toHaveLength(1);
    expect(profileErrors({ ...draft, initialPrompt: ` ${"p".repeat(4000)} ` })).toEqual([]);
    expect(profileErrors({ ...draft, initialPrompt: "p".repeat(4001) })).toHaveLength(1);
  });

  it("so considera alterado o que muda depois de normalizar", () => {
    const draft = profileDraftFrom(ASSISTANT);
    expect(profileChanged(draft, ASSISTANT)).toBe(false);
    expect(profileChanged({ ...draft, name: " Assistente jurídico " }, ASSISTANT)).toBe(false);
    expect(profileChanged({ ...draft, initialPrompt: "" }, ASSISTANT)).toBe(true);
    expect(profileChanged({ ...draft, description: "Outra" }, ASSISTANT)).toBe(true);
  });

  it("avisa nome repetido sem diferenciar maiusculas, ignorando o proprio (D8)", () => {
    const others: Assistant[] = [ASSISTANT, { ...ASSISTANT, id: "rh", name: "RH" }];
    const draft = profileDraftFrom(ASSISTANT);
    expect(duplicateNameWarning(draft, others, "juridico")).toBeNull();
    expect(duplicateNameWarning({ ...draft, name: " rh " }, others, "juridico")).not.toBeNull();
  });

  it("libera o card ao admin e ao curador do assistente (D1)", () => {
    expect(canEditAssistantProfile({ ...MENU, manageAssistants: true }, { ...ASSISTANT, groups: [] })).toBe(true);
    expect(canEditAssistantProfile({ ...MENU, manageDocuments: true }, ASSISTANT)).toBe(true);
    expect(canEditAssistantProfile({ ...MENU, manageDocuments: true }, { ...ASSISTANT, groups: [] })).toBe(false);
    expect(canEditAssistantProfile(MENU, ASSISTANT)).toBe(false);
    expect(canEditAssistantProfile({ ...MENU, manageAssistants: true }, null)).toBe(false);
  });

  it("traduz o code da API e cai na mensagem generica sem code", () => {
    const tooLong = { error: { detail: { code: "assistant_prompt_too_long", message: "x" } } };
    expect(describeProfileError(tooLong)).toContain("4000");
    const forbidden = { error: { detail: "you do not have permission", code: "forbidden" } };
    expect(describeProfileError(forbidden)).toContain("permissão");
    expect(describeProfileError({ error: { detail: "Falhou." } })).toBe("Falhou.");
  });
});
