import { A11yModule } from "@angular/cdk/a11y";
import { CommonModule } from "@angular/common";
import { Component, computed, effect, input, output, signal, untracked } from "@angular/core";

import {
  HomeCards,
  HomeDraft,
  canSave,
  counterLabel,
  draftFrom,
  isSelected,
  isToggleDisabled,
  setDefault,
  toggleAssistant
} from "../../shared/home/home-assistants";
import { Assistant } from "../../shared/models/nexus.models";

let nextId = 0;

/**
 * SPEC-016 (RF-107, D3): modal "Personalizar acesso rapido".
 *
 * Mesmo padrao visual e de foco do modal da SPEC-014. Cada linha tem a caixa de
 * acesso rapido e o radio "Padrao", habilitado so nas linhas marcadas. As regras
 * ficam em ``shared/home/home-assistants.ts``.
 */
@Component({
  selector: "app-home-assistants-dialog",
  standalone: true,
  imports: [CommonModule, A11yModule],
  host: { "(document:keydown.escape)": "dismiss()" },
  template: `
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
      (mousedown)="pressedBackdrop = $event.target === $event.currentTarget"
      (click)="onBackdropClick($event)"
    >
      <article
        role="dialog"
        aria-modal="true"
        [attr.aria-labelledby]="titleId"
        [attr.aria-describedby]="descriptionId"
        [attr.aria-busy]="saving()"
        cdkTrapFocus
        [cdkTrapFocusAutoCapture]="true"
        class="flex max-h-[90vh] w-full max-w-lg flex-col rounded-3xl border border-slate-800 bg-slate-900 p-6 text-nexus-text shadow-2xl"
        data-testid="home-assistants-dialog"
      >
        <header class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <h2 [id]="titleId" class="text-lg font-semibold">Personalizar acesso rápido</h2>
            <p [id]="descriptionId" class="mt-1 text-sm text-slate-400">
              Escolha até {{ cards().max }} assistentes para a tela inicial e marque o padrão,
              que já vem selecionado ao abrir o Nexus.
            </p>
          </div>
          <span
            class="shrink-0 rounded-full bg-slate-800 px-3 py-1 text-xs font-medium text-slate-300"
            aria-live="polite"
            data-testid="home-assistants-counter"
          >
            {{ counter() }}
          </span>
        </header>

        <ul class="mt-5 -mx-2 flex-1 space-y-1 overflow-y-auto px-2" role="list">
          <li
            *ngFor="let assistant of assistants()"
            class="flex items-center gap-3 rounded-2xl px-3 py-2 transition-colors"
            [ngClass]="selected(assistant.id) ? 'bg-nexus-accent/10' : 'hover:bg-nexus-hover'"
          >
            <input
              type="checkbox"
              [id]="checkboxId(assistant.id)"
              [checked]="selected(assistant.id)"
              [disabled]="saving() || toggleDisabled(assistant.id)"
              (change)="toggle(assistant.id)"
              class="h-4 w-4 shrink-0 accent-nexus-accent disabled:cursor-not-allowed"
            />
            <label
              [for]="checkboxId(assistant.id)"
              class="min-w-0 flex-1 cursor-pointer"
              [class.opacity-50]="toggleDisabled(assistant.id)"
            >
              <span class="block truncate text-sm font-medium">{{ assistant.name }}</span>
              <span class="block truncate text-xs text-nexus-dim">
                {{ assistant.description || "Assistente sem descricao configurada." }}
              </span>
            </label>
            <label
              class="flex shrink-0 items-center gap-1.5 text-xs"
              [ngClass]="selected(assistant.id) ? 'cursor-pointer text-slate-300' : 'text-slate-600'"
            >
              <input
                type="radio"
                [name]="radioName"
                [checked]="draft().defaultId === assistant.id"
                [disabled]="saving() || !selected(assistant.id)"
                (change)="chooseDefault(assistant.id)"
                [attr.aria-label]="'Padrão: ' + assistant.name"
                class="h-4 w-4 accent-nexus-accent"
              />
              Padrão
            </label>
          </li>
        </ul>

        <p *ngIf="!valid()" class="mt-3 text-xs text-amber-200" role="status">
          Marque pelo menos um assistente e escolha o padrão.
        </p>
        <p
          *ngIf="error()"
          role="alert"
          class="mt-4 rounded-2xl border border-rose-400/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
        >
          {{ error() }}
        </p>

        <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            [disabled]="saving()"
            (click)="dismiss()"
            class="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-nexus-hover disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            [disabled]="saving() || !valid()"
            (click)="submit()"
            class="rounded-full bg-nexus-accent px-5 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="home-assistants-save"
          >
            {{ saving() ? "Salvando..." : "Salvar" }}
          </button>
        </div>
      </article>
    </div>
  `
})
export class HomeAssistantsDialogComponent {
  readonly assistants = input.required<Assistant[]>();
  readonly cards = input.required<HomeCards>();
  readonly saving = input(false);
  readonly error = input<string | null>(null);

  readonly save = output<{ assistantIds: string[]; defaultAssistantId: string }>();
  readonly cancel = output<void>();

  private readonly id = nextId++;
  protected readonly titleId = `home-assistants-title-${this.id}`;
  protected readonly descriptionId = `home-assistants-description-${this.id}`;
  protected readonly radioName = `home-assistants-default-${this.id}`;
  protected pressedBackdrop = false;

  protected readonly draft = signal<HomeDraft>({ selected: [], defaultId: null });
  protected readonly valid = computed(() => canSave(this.draft(), this.cards().max));
  protected readonly counter = computed(() => counterLabel(this.draft(), this.cards().max));

  constructor() {
    // O rascunho parte do que esta na tela quando o modal abre.
    effect(() => {
      const cards = this.cards();
      untracked(() => this.draft.set(draftFrom(cards)));
    });
  }

  protected checkboxId(assistantId: string): string {
    return `home-assistant-${this.id}-${assistantId}`;
  }

  protected selected(assistantId: string): boolean {
    return isSelected(this.draft(), assistantId);
  }

  protected toggleDisabled(assistantId: string): boolean {
    return isToggleDisabled(this.draft(), assistantId, this.cards().max);
  }

  protected toggle(assistantId: string): void {
    this.draft.update((draft) => toggleAssistant(draft, assistantId, this.cards().max));
  }

  protected chooseDefault(assistantId: string): void {
    this.draft.update((draft) => setDefault(draft, assistantId));
  }

  protected submit(): void {
    const draft = this.draft();
    if (this.saving() || !this.valid() || draft.defaultId === null) {
      return;
    }
    this.save.emit({ assistantIds: [...draft.selected], defaultAssistantId: draft.defaultId });
  }

  protected dismiss(): void {
    if (!this.saving()) {
      this.cancel.emit();
    }
  }

  protected onBackdropClick(event: MouseEvent): void {
    if (this.pressedBackdrop && event.target === event.currentTarget) {
      this.dismiss();
    }
    this.pressedBackdrop = false;
  }
}
