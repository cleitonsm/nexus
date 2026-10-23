import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";

import { selectedGroups, toggleGroup, unknownGroups } from "./group-selection";

/**
 * Escolha de grupos do Keycloak (decisao PC-D6). Sem a lista (Keycloak fora
 * do ar ou cliente de servico nao configurado), volta ao campo de texto.
 * O valor e sempre o texto separado por virgulas, como antes.
 */
@Component({
  selector: "app-group-picker",
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="w-full">
      <ng-container *ngIf="available !== null; else freeText">
        <div class="flex flex-wrap gap-2" role="group" [attr.aria-label]="label">
          <button
            *ngFor="let group of available"
            type="button"
            (click)="toggle(group)"
            [attr.aria-pressed]="isSelected(group)"
            class="rounded-full border px-3 py-1 text-xs transition-colors"
            [ngClass]="
              isSelected(group)
                ? 'border-indigo-400 bg-indigo-500/20 text-indigo-100'
                : 'border-slate-700 text-slate-300 hover:bg-nexus-hover'
            "
          >
            {{ group }}
          </button>
          <button
            *ngFor="let group of unknown()"
            type="button"
            (click)="toggle(group)"
            aria-pressed="true"
            title="Grupo que não existe no Keycloak; clique para remover"
            class="rounded-full border border-amber-400/60 bg-amber-500/10 px-3 py-1 text-xs text-amber-100"
          >
            {{ group }} (fora do Keycloak) ×
          </button>
          <span *ngIf="available.length === 0" class="text-xs text-slate-400">
            Nenhum grupo cadastrado no Keycloak.
          </span>
        </div>
        <p *ngIf="selected().length === 0" class="mt-1 text-xs text-slate-500">{{ emptyHint }}</p>
      </ng-container>
      <ng-template #freeText>
        <input
          type="text"
          [attr.aria-label]="label"
          class="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm outline-none focus:border-indigo-400"
          [placeholder]="placeholder"
          [value]="value"
          (input)="onInput($event)"
        />
      </ng-template>
    </div>
  `
})
export class GroupPickerComponent {
  /** Grupos do Keycloak; ``null`` quando a lista nao esta disponivel. */
  @Input() available: string[] | null = null;
  @Input() value = "";
  @Input() label = "Grupos";
  @Input() placeholder = "Ex: rh, financeiro";
  @Input() emptyHint = "Nenhum grupo marcado.";
  @Output() readonly valueChange = new EventEmitter<string>();

  protected selected(): string[] {
    return selectedGroups(this.value);
  }

  protected isSelected(group: string): boolean {
    return this.selected().includes(group);
  }

  protected unknown(): string[] {
    return unknownGroups(this.value, this.available ?? []);
  }

  protected toggle(group: string): void {
    this.valueChange.emit(toggleGroup(this.value, group));
  }

  protected onInput(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    this.valueChange.emit(target?.value ?? "");
  }
}
