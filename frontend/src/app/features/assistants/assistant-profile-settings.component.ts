import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, input, signal, untracked } from "@angular/core";
import { Store } from "@ngrx/store";

import {
  AssistantProfileDraft,
  PROFILE_LIMITS,
  ProfileField,
  duplicateNameWarning,
  profileChanged,
  profileDraftFrom,
  profileErrors,
  profileFieldLength,
  profileInputFrom
} from "../../shared/assistants/assistant-profile";
import { nexusActions } from "../../store/nexus.actions";
import { selectAssistants, selectLoadingState } from "../../store/nexus.selectors";

const EMPTY_DRAFT: AssistantProfileDraft = { name: "", description: "", initialPrompt: "" };

/**
 * "Dados do assistente" (SPEC-017, RF-110): nome, descricao e prompt inicial.
 * Administrador e curador do assistente editam (D1); a API repete a verificacao.
 * O erro da API aparece no aviso da pagina; aqui ficam as regras locais (RN-51).
 */
@Component({
  selector: "app-assistant-profile-settings",
  standalone: true,
  imports: [CommonModule],
  template: `
    <article
      class="rounded-3xl border border-slate-800 bg-slate-900/70 p-4"
      data-testid="assistant-profile"
    >
      <h2 class="text-lg font-semibold">Dados do assistente</h2>
      <p class="mt-1 text-sm text-slate-400">
        Nome, descrição e prompt valem a partir da próxima pergunta, inclusive nas conversas
        abertas. Grupos, documentos e índice não mudam.
      </p>

      <div class="mt-4 space-y-4">
        <label class="block text-sm text-slate-300" [attr.for]="fieldId('name')">
          <span class="flex items-center justify-between gap-2">
            <span>Nome</span>
            <span class="text-xs" [ngClass]="counterClass('name')">{{ counter("name") }}</span>
          </span>
          <input
            type="text"
            [id]="fieldId('name')"
            class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            [value]="draft().name"
            (input)="update('name', $any($event.target).value)"
            autocomplete="off"
          />
        </label>
        <p
          *ngIf="duplicateWarning() as warning"
          class="-mt-2 text-xs text-amber-200"
          role="status"
        >
          {{ warning }}
        </p>

        <label class="block text-sm text-slate-300" [attr.for]="fieldId('description')">
          <span class="flex items-center justify-between gap-2">
            <span>Descrição</span>
            <span class="text-xs" [ngClass]="counterClass('description')">
              {{ counter("description") }}
            </span>
          </span>
          <textarea
            [id]="fieldId('description')"
            rows="2"
            class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            [value]="draft().description"
            (input)="update('description', $any($event.target).value)"
          ></textarea>
          <span class="mt-1 block text-xs text-slate-500">
            Aparece nos cartões da tela inicial e ajuda a escolher o assistente automaticamente.
          </span>
        </label>

        <label class="block text-sm text-slate-300" [attr.for]="fieldId('initialPrompt')">
          <span class="flex items-center justify-between gap-2">
            <span>Prompt inicial</span>
            <span class="text-xs" [ngClass]="counterClass('initialPrompt')">
              {{ counter("initialPrompt") }}
            </span>
          </span>
          <textarea
            [id]="fieldId('initialPrompt')"
            rows="8"
            class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs leading-relaxed"
            [value]="draft().initialPrompt"
            (input)="update('initialPrompt', $any($event.target).value)"
          ></textarea>
          <span class="mt-1 block text-xs text-slate-500">
            As regras de citação e de formato da resposta são sempre aplicadas depois do prompt.
          </span>
        </label>
        <p
          *ngIf="!draft().initialPrompt.trim()"
          class="-mt-2 rounded-2xl border border-sky-400/40 bg-sky-500/10 px-4 py-2 text-xs text-sky-100"
        >
          Sem prompt, o assistente usa a instrução padrão do sistema.
        </p>
      </div>

      <ul *ngIf="errors().length" class="mt-3 space-y-1 text-xs text-rose-300" role="alert">
        <li *ngFor="let message of errors()">{{ message }}</li>
      </ul>

      <div class="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          (click)="save()"
          [disabled]="!canSave()"
          class="rounded-full bg-indigo-500 px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
          data-testid="assistant-profile-save"
        >
          {{ saving() ? "Salvando..." : "Salvar" }}
        </button>
        <button
          type="button"
          (click)="discard()"
          [disabled]="!dirty() || saving()"
          class="rounded-full border border-slate-700 px-5 py-2 text-sm disabled:opacity-50"
        >
          Descartar
        </button>
      </div>
    </article>
  `
})
export class AssistantProfileSettingsComponent {
  private readonly store = inject(Store);

  readonly assistantId = input.required<string>();

  private readonly assistants = this.store.selectSignal(selectAssistants);
  private readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly assistant = computed(
    () => this.assistants().find((item) => item.id === this.assistantId()) ?? null
  );

  protected readonly draft = signal<AssistantProfileDraft>({ ...EMPTY_DRAFT });
  protected readonly errors = computed(() => profileErrors(this.draft()));
  protected readonly saving = computed(() => this.loading().updateAssistant);
  protected readonly dirty = computed(() => {
    const current = this.assistant();
    return !!current && profileChanged(this.draft(), current);
  });
  protected readonly canSave = computed(
    () => this.dirty() && this.errors().length === 0 && !this.saving()
  );
  protected readonly duplicateWarning = computed(() =>
    duplicateNameWarning(this.draft(), this.assistants(), this.assistantId())
  );

  constructor() {
    // Outro assistente ou o gravado acabou de mudar: o formulario recomeca dele.
    effect(() => {
      const current = this.assistant();
      untracked(() => this.draft.set(current ? profileDraftFrom(current) : { ...EMPTY_DRAFT }));
    });
  }

  protected fieldId(field: ProfileField): string {
    return `assistant-${field}-${this.assistantId()}`;
  }

  protected counter(field: ProfileField): string {
    return `${profileFieldLength(this.draft(), field)} / ${PROFILE_LIMITS[field]}`;
  }

  protected counterClass(field: ProfileField): string {
    return profileFieldLength(this.draft(), field) > PROFILE_LIMITS[field]
      ? "text-rose-300"
      : "text-slate-500";
  }

  protected update(field: ProfileField, value: string): void {
    this.draft.update((draft) => ({ ...draft, [field]: value }));
  }

  protected discard(): void {
    const current = this.assistant();
    if (current) {
      this.draft.set(profileDraftFrom(current));
    }
  }

  protected save(): void {
    if (!this.canSave()) {
      return;
    }
    this.store.dispatch(
      nexusActions.updateAssistant({
        assistantId: this.assistantId(),
        input: profileInputFrom(this.draft())
      })
    );
  }
}
