import { describe, expect, it } from "vitest";

import { selectedGroups, toggleGroup, unknownGroups } from "./group-selection";

describe("group selection (PC-D6)", () => {
  it("toggles a group keeping the comma-separated format sorted", () => {
    expect(toggleGroup("", "rh")).toBe("rh");
    expect(toggleGroup("rh", "financeiro")).toBe("financeiro, rh");
    expect(toggleGroup("financeiro, rh", "rh")).toBe("financeiro");
    expect(toggleGroup("rh", "rh")).toBe("");
  });

  it("reads the selected groups from free text", () => {
    expect(selectedGroups(" rh, /diretoria ,, rh")).toEqual(["diretoria", "rh"]);
  });

  it("keeps groups typed before the list as unknown so they can be removed", () => {
    expect(unknownGroups("rh, antigo", ["rh", "financeiro"])).toEqual(["antigo"]);
    expect(unknownGroups("", ["rh"])).toEqual([]);
  });
});
