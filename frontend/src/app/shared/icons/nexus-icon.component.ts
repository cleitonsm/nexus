import { ChangeDetectionStrategy, Component, computed, input } from "@angular/core";

import { IconShapes, NEXUS_ICONS, NexusIconName } from "./nexus-icons";

/**
 * SPEC-015 (D2): `<nexus-icon name="newChat" />`. Traco 1,75 e cor do texto (`currentColor`).
 * `name="logo"` desenha a marca "N" do Nexus, a mesma do `favicon.svg`.
 */
@Component({
  selector: "nexus-icon",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: "inline-flex shrink-0", "aria-hidden": "true" },
  template: `
    @if (name() === "logo") {
      <svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 32 32">
        <rect width="32" height="32" rx="9" fill="#4f46e5" />
        <path d="M10 22V10l12 12V10" fill="none" stroke="#f1f5f9" stroke-width="2.6"
          stroke-linecap="round" stroke-linejoin="round" />
        <g fill="#f1f5f9">
          <circle cx="10" cy="10" r="2.6" />
          <circle cx="10" cy="22" r="2.6" />
          <circle cx="22" cy="10" r="2.6" />
          <circle cx="22" cy="22" r="2.6" />
        </g>
      </svg>
    } @else if (shapes(); as icon) {
      <svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" [attr.stroke-width]="strokeWidth()"
        stroke-linecap="round" stroke-linejoin="round">
        @for (d of icon.paths; track $index) {
          <path [attr.d]="d" />
        }
        @for (rect of icon.rects ?? []; track $index) {
          <rect [attr.x]="rect.x" [attr.y]="rect.y" [attr.width]="rect.w" [attr.height]="rect.h"
            [attr.rx]="rect.r" />
        }
        @for (circle of icon.circles ?? []; track $index) {
          <circle [attr.cx]="circle.cx" [attr.cy]="circle.cy" [attr.r]="circle.r" />
        }
      </svg>
    }
  `
})
export class NexusIconComponent {
  readonly name = input.required<NexusIconName>();
  readonly size = input(20);
  readonly strokeWidth = input(1.75);

  protected readonly shapes = computed<IconShapes | null>(() => {
    const name = this.name();
    return name === "logo" ? null : NEXUS_ICONS[name];
  });
}
