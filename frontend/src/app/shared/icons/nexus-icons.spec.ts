import { describe, expect, it } from "vitest";

import { NEXUS_ICONS } from "./nexus-icons";

describe("nexus icons (SPEC-015, D2)", () => {
  it("covers every administration screen and the sidebar items", () => {
    const required = [
      "newChat", "assistants", "recent", "settings", "logout", "panelOpen", "panelClose",
      "documents", "audit", "archived", "feedback", "usage", "llmCredentials"
    ];
    for (const name of required) {
      expect(NEXUS_ICONS).toHaveProperty(name);
    }
  });

  it("draws every icon in the 24x24 box with at least one shape", () => {
    for (const icon of Object.values(NEXUS_ICONS)) {
      const shapes = icon.paths.length + ("rects" in icon ? icon.rects.length : 0)
        + ("circles" in icon ? icon.circles.length : 0);
      expect(shapes).toBeGreaterThan(0);
    }
  });
});
