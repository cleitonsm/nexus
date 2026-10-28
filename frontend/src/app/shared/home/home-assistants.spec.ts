import { describe, expect, it } from "vitest";

import { Assistant, HomeAssistants } from "../models/nexus.models";
import {
  canSave,
  counterLabel,
  draftFrom,
  isToggleDisabled,
  newConversationAssistant,
  resolveHomeCards,
  setDefault,
  toggleAssistant
} from "./home-assistants";

function assistant(id: string): Assistant {
  return { id, name: id, description: null, initial_prompt: null, created_at: "2026-10-28T00:00:00Z" };
}

const ALL = ["a", "b", "c", "d", "e"].map(assistant);

function home(overrides: Partial<HomeAssistants> = {}): HomeAssistants {
  return { assistant_ids: ["c", "a"], default_assistant_id: "c", max: 4, customized: true, ...overrides };
}

describe("resolveHomeCards (CT-128, RN-49)", () => {
  it("uses the API answer with the default first", () => {
    const cards = resolveHomeCards(ALL, home({ assistant_ids: ["a", "c"], default_assistant_id: "c" }));
    expect(cards.assistants.map((item) => item.id)).toEqual(["c", "a"]);
    expect(cards.defaultId).toBe("c");
    expect(cards.customized).toBe(true);
  });

  it("falls back to the first four before the API answers (D4)", () => {
    const cards = resolveHomeCards(ALL, null);
    expect(cards.assistants.map((item) => item.id)).toEqual(["a", "b", "c", "d"]);
    expect(cards.defaultId).toBe("a");
    expect(cards.customized).toBe(false);
  });

  it("drops assistants the local list no longer has (D8)", () => {
    const cards = resolveHomeCards(ALL.slice(0, 2), home({ assistant_ids: ["c", "a"], default_assistant_id: "c" }));
    expect(cards.assistants.map((item) => item.id)).toEqual(["a"]);
    expect(cards.defaultId).toBe("a");
  });

  it("shows nothing without assistants", () => {
    const cards = resolveHomeCards([], null);
    expect(cards.assistants).toEqual([]);
    expect(cards.defaultId).toBeNull();
  });
});

describe("home assistants draft (CT-128, RN-47, RF-107)", () => {
  const start = draftFrom(resolveHomeCards(ALL, home()));

  it("starts from the cards on screen", () => {
    expect(start).toEqual({ selected: ["c", "a"], defaultId: "c" });
    expect(counterLabel(start, 4)).toBe("2 de 4");
  });

  it("adds in marking order and blocks above the limit", () => {
    let draft = toggleAssistant(start, "e", 4);
    draft = toggleAssistant(draft, "b", 4);
    expect(draft.selected).toEqual(["c", "a", "e", "b"]);
    expect(isToggleDisabled(draft, "d", 4)).toBe(true);
    expect(isToggleDisabled(draft, "a", 4)).toBe(false);
    expect(toggleAssistant(draft, "d", 4)).toBe(draft);
    expect(counterLabel(draft, 4)).toBe("4 de 4");
  });

  it("moves the default to the first remaining when it is unmarked", () => {
    const draft = toggleAssistant(start, "c", 4);
    expect(draft).toEqual({ selected: ["a"], defaultId: "a" });
  });

  it("the first marked becomes default when none is left", () => {
    let draft = toggleAssistant(start, "c", 4);
    draft = toggleAssistant(draft, "a", 4);
    expect(draft).toEqual({ selected: [], defaultId: null });
    expect(canSave(draft, 4)).toBe(false);
    draft = toggleAssistant(draft, "d", 4);
    expect(draft).toEqual({ selected: ["d"], defaultId: "d" });
    expect(canSave(draft, 4)).toBe(true);
  });

  it("only a marked assistant can be the default", () => {
    expect(setDefault(start, "e")).toBe(start);
    expect(setDefault(start, "a").defaultId).toBe("a");
  });

  it("refuses a draft above the limit", () => {
    expect(canSave({ selected: ["a", "b", "c", "d", "e"], defaultId: "a" }, 4)).toBe(false);
    expect(canSave({ selected: ["a"], defaultId: "b" }, 4)).toBe(false);
  });
});

describe("newConversationAssistant (D5)", () => {
  it("returns to the default and keeps the active without one", () => {
    expect(newConversationAssistant("a", "b")).toBe("a");
    expect(newConversationAssistant(null, "b")).toBe("b");
    expect(newConversationAssistant(null, null)).toBeNull();
  });
});
