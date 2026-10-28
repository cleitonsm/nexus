import { A11yModule } from "@angular/cdk/a11y";
import { CommonModule } from "@angular/common";
import { Component, computed, input, output, signal } from "@angular/core";

import { ConfirmDialogConfig, canConfirm, canDismiss } from "./confirm-dialog";

let nextId = 0;

/**
 * SPEC-014: modal de confirmacao no padrao visual do Nexus (RF-97 a RF-99).
 *
 * Substitui o ``window.confirm``. Foco preso no modal e devolvido ao fechar;
 * Esc, clique no fundo e Cancelar fecham, exceto durante a exclusao.
 */
@Component({
  selector: "app-confirm-dialog",
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
        role="alertdialog"
        aria-modal="true"
        [attr.aria-labelledby]="titleId"
        [attr.aria-describedby]="messageId"
        [attr.aria-busy]="busy()"
        cdkTrapFocus
        [cdkTrapFocusAutoCapture]="true"
        class="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900 p-6 text-nexus-text shadow-2xl"
        data-testid="confirm-dialog"
      >
        <div class="flex items-start gap-4">
          <div
            class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-rose-500/15 text-rose-300"
            aria-hidden="true"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 6h18" />
              <path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <h2 [id]="titleId" class="break-words text-lg font-semibold">{{ config().title }}</h2>
            <p [id]="messageId" class="mt-1 text-sm text-slate-400">{{ config().message }}</p>
          </div>
        </div>

        <div
          *ngIf="config().warning as warning"
          class="mt-5 rounded-2xl border border-amber-400/40 bg-amber-500/10 p-4 text-sm text-amber-100"
          data-testid="confirm-dialog-warning"
        >
          <p class="flex items-start gap-2 font-medium">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mt-0.5 shrink-0" aria-hidden="true">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              <path d="M12 9v4M12 17h.01" />
            </svg>
            <span>{{ warning }}</span>
          </p>
          <ul *ngIf="config().consequences.length > 0" class="mt-2 list-disc space-y-1 pl-10 text-amber-100/90">
            <li *ngFor="let item of config().consequences">{{ item }}</li>
          </ul>
        </div>

        <label *ngIf="config().requireText as expected" class="mt-5 block text-sm text-slate-300">
          Para confirmar, digite
          <strong class="select-all font-semibold text-nexus-text">{{ expected }}</strong>
          abaixo.
          <input
            cdkFocusInitial
            type="text"
            autocomplete="off"
            spellcheck="false"
            [value]="typed()"
            [disabled]="busy()"
            (input)="onTyped($event)"
            (keydown.enter)="confirm()"
            [attr.aria-label]="'Digite ' + expected + ' para confirmar'"
            class="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none transition-colors focus:border-rose-400 disabled:opacity-60"
            data-testid="confirm-dialog-input"
          />
        </label>

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
            [attr.cdkFocusInitial]="config().requireText ? null : ''"
            [disabled]="busy()"
            (click)="dismiss()"
            class="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-nexus-hover disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            [disabled]="!confirmEnabled()"
            (click)="confirm()"
            class="rounded-full bg-rose-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="confirm-dialog-confirm"
          >
            {{ busy() ? config().busyLabel : config().confirmLabel }}
          </button>
        </div>
      </article>
    </div>
  `
})
export class ConfirmDialogComponent {
  readonly config = input.required<ConfirmDialogConfig>();
  readonly busy = input(false);
  readonly error = input<string | null>(null);

  readonly confirmed = output<void>();
  readonly cancelled = output<void>();

  protected readonly titleId = `confirm-dialog-title-${++nextId}`;
  protected readonly messageId = `confirm-dialog-message-${nextId}`;
  protected readonly typed = signal("");
  protected readonly confirmEnabled = computed(() =>
    canConfirm(this.config(), this.typed(), this.busy())
  );

  /** Clique que comecou e terminou no fundo (arrastar do campo nao fecha). */
  protected pressedBackdrop = false;

  protected onTyped(event: Event): void {
    this.typed.set((event.target as HTMLInputElement).value);
  }

  protected onBackdropClick(event: MouseEvent): void {
    if (this.pressedBackdrop && event.target === event.currentTarget) {
      this.dismiss();
    }
    this.pressedBackdrop = false;
  }

  protected confirm(): void {
    if (this.confirmEnabled()) {
      this.confirmed.emit();
    }
  }

  protected dismiss(): void {
    if (canDismiss(this.busy())) {
      this.cancelled.emit();
    }
  }
}
