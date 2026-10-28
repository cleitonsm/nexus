/** SPEC-015 (RF-102): nomes acessiveis e tooltips do topo da barra lateral. */
export const OPEN_SIDEBAR_LABEL = "Abrir barra lateral";
export const CLOSE_SIDEBAR_LABEL = "Fechar barra lateral";

/** Rotulo do botao do topo conforme a barra esteja aberta ou recolhida. */
export function sidebarToggleLabel(contentVisible: boolean): string {
  return contentVisible ? CLOSE_SIDEBAR_LABEL : OPEN_SIDEBAR_LABEL;
}

/** RF-101: os itens so mostram tooltip com a barra recolhida. */
export function itemTooltipDisabled(contentVisible: boolean): boolean {
  return contentVisible;
}

/** D4: secoes que a barra recolhida abre ao clicar no icone. */
export type SidebarSection = "assistants" | "conversations";
