import { ConnectedPosition } from "@angular/cdk/overlay";

/** SPEC-015 (D5): de que lado do elemento o tooltip abre primeiro. */
export type TooltipPlacement = "right" | "bottom";

const RIGHT: ConnectedPosition = {
  originX: "end",
  originY: "center",
  overlayX: "start",
  overlayY: "center",
  offsetX: 12
};

const BOTTOM: ConnectedPosition = {
  originX: "center",
  originY: "bottom",
  overlayX: "center",
  overlayY: "top",
  offsetY: 8
};

/** Posicoes do overlay: a preferida primeiro e a outra como alternativa. */
export function tooltipPositions(placement: TooltipPlacement): ConnectedPosition[] {
  return placement === "right" ? [RIGHT, BOTTOM] : [BOTTOM, RIGHT];
}

/** O tooltip so abre com texto e quando nao foi desativado. */
export function tooltipEnabled(text: string | null | undefined, disabled: boolean): boolean {
  return !disabled && (text ?? "").trim().length > 0;
}
