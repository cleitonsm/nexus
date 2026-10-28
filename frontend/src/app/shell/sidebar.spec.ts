import { describe, expect, it } from "vitest";

import { tooltipEnabled, tooltipPositions } from "../shared/tooltip/tooltip";
import {
  CLOSE_SIDEBAR_LABEL,
  OPEN_SIDEBAR_LABEL,
  itemTooltipDisabled,
  sidebarToggleLabel
} from "./sidebar";

describe("sidebar header and tooltips (SPEC-015, CT-120)", () => {
  it("names the toggle after what it does", () => {
    expect(sidebarToggleLabel(false)).toBe(OPEN_SIDEBAR_LABEL);
    expect(sidebarToggleLabel(true)).toBe(CLOSE_SIDEBAR_LABEL);
    expect(OPEN_SIDEBAR_LABEL).toBe("Abrir barra lateral");
    expect(CLOSE_SIDEBAR_LABEL).toBe("Fechar barra lateral");
  });

  it("shows item tooltips only while the sidebar is collapsed (RF-101)", () => {
    expect(itemTooltipDisabled(false)).toBe(false);
    expect(itemTooltipDisabled(true)).toBe(true);
  });
});

describe("tooltip rules (SPEC-015, CT-121)", () => {
  it("opens to the right first and falls back below", () => {
    const [first, second] = tooltipPositions("right");
    expect(first).toMatchObject({ originX: "end", overlayX: "start", originY: "center" });
    expect(second).toMatchObject({ originY: "bottom", overlayY: "top" });
    expect(tooltipPositions("bottom")[0]).toMatchObject({ originY: "bottom" });
  });

  it("needs text and must not be disabled", () => {
    expect(tooltipEnabled("Nova conversa", false)).toBe(true);
    expect(tooltipEnabled("Nova conversa", true)).toBe(false);
    expect(tooltipEnabled("  ", false)).toBe(false);
    expect(tooltipEnabled(null, false)).toBe(false);
  });
});
