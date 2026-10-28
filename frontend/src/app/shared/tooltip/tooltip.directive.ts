import { Overlay, OverlayRef } from "@angular/cdk/overlay";
import { ComponentPortal } from "@angular/cdk/portal";
import {
  ChangeDetectionStrategy,
  Component,
  Directive,
  ElementRef,
  OnDestroy,
  effect,
  inject,
  input,
  signal
} from "@angular/core";

import { TooltipPlacement, tooltipEnabled, tooltipPositions } from "./tooltip";

/** Pilula clara no padrao do Gemini (SPEC-015, D5). */
@Component({
  selector: "nexus-tooltip-panel",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      role="tooltip"
      class="pointer-events-none whitespace-nowrap rounded-lg bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-900 shadow-lg"
    >{{ text() }}</div>
  `
})
export class TooltipPanelComponent {
  readonly text = signal("");
}

/**
 * SPEC-015 (D5): `<button nexusTooltip="Nova conversa">`. Abre no hover e no foco pelo
 * teclado; fecha ao sair, ao clicar ou quando `nexusTooltipDisabled` vira verdadeiro.
 * Usa o CDK Overlay para nao ser cortado pela barra lateral.
 */
@Directive({
  selector: "[nexusTooltip]",
  standalone: true,
  host: {
    "(mouseenter)": "show()",
    "(mouseleave)": "hide()",
    "(focusin)": "show()",
    "(focusout)": "hide()",
    "(click)": "hide()",
    "(keydown.escape)": "hide()"
  }
})
export class TooltipDirective implements OnDestroy {
  readonly nexusTooltip = input<string | null>("");
  readonly nexusTooltipDisabled = input(false);
  readonly nexusTooltipPlacement = input<TooltipPlacement>("right");

  private readonly overlay = inject(Overlay);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private overlayRef: OverlayRef | null = null;

  constructor() {
    effect(() => {
      if (!tooltipEnabled(this.nexusTooltip(), this.nexusTooltipDisabled())) {
        this.hide();
      }
    });
  }

  show(): void {
    const text = this.nexusTooltip();
    if (!tooltipEnabled(text, this.nexusTooltipDisabled()) || this.overlayRef) {
      return;
    }
    const positionStrategy = this.overlay
      .position()
      .flexibleConnectedTo(this.host)
      .withPositions(tooltipPositions(this.nexusTooltipPlacement()))
      .withPush(false);
    this.overlayRef = this.overlay.create({
      positionStrategy,
      scrollStrategy: this.overlay.scrollStrategies.close(),
      panelClass: "nexus-tooltip-pane"
    });
    const panel = this.overlayRef.attach(new ComponentPortal(TooltipPanelComponent));
    panel.instance.text.set(text ?? "");
  }

  hide(): void {
    this.overlayRef?.dispose();
    this.overlayRef = null;
  }

  ngOnDestroy(): void {
    this.hide();
  }
}
