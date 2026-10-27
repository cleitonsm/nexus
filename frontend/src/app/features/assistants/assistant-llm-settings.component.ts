import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, input, signal, untracked } from "@angular/core";
import { Store } from "@ngrx/store";

import { llmSourceLabel, providerLabel } from "../../shared/llm/llm-config";
import { selectMenu } from "../../store/auth.selectors";
import { llmConfigActions } from "../../store/llm-config.actions";
import {
  selectAssistantLlmById,
  selectDefaultLlmOption,
  selectLlmLoading,
  selectLlmOptions
} from "../../store/llm-config.selectors";

/**
 * "Modelo de linguagem" do assistente (SPEC-013, RF-90, RF-92). O administrador
 * escolhe credencial e modelo (D7); o curador so ve o que vale (T8). Vazio =
 * segue a credencial padrao; com modelo e sem credencial, recua ao modelo
 * padrao dela se a padrao mudar e nao tiver o modelo (D11).
 */
@Component({
  selector: "app-assistant-llm-settings",
  standalone: true,
  imports: [CommonModule],
  template: `
    <article class="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
      <h2 class="text-lg font-semibold">Modelo de linguagem</h2>
      <ng-container *ngIf="llm() as current; else loadingLlm">
        <p class="mt-1 text-sm text-slate-400">
          Em uso: <span class="text-slate-200">{{ current.effective_credential_name ?? "ambiente" }}</span>
          · {{ providerLabel(current.effective_provider) }} ·
          <span class="font-mono text-slate-200">{{ current.effective_model }}</span>
          <span class="text-xs text-slate-500"> ({{ sourceLabel(current.source) }})</span>
        </p>
        <p
          *ngIf="current.model_falls_back"
          class="mt-2 rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100"
        >
          O modelo escolhido ({{ current.model }}) não existe na credencial padrão atual; as respostas
          usam o modelo padrão dela.
        </p>
        <p
          *ngIf="current.source === 'environment'"
          class="mt-2 rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100"
        >
          Nenhuma chave de LLM cadastrada. Cadastre uma em Administração › Chaves de LLM.
        </p>

        <div *ngIf="canEdit()" class="mt-4 flex flex-wrap items-end gap-3">
          <label class="block text-xs text-slate-300">
            Chave
            <select
              class="mt-1 w-64 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              [value]="credentialId()"
              (change)="onCredentialChange($any($event.target).value)"
            >
              <option value="">Padrão do sistema{{ defaultOption() ? " (" + defaultOption()!.name + ")" : "" }}</option>
              <option *ngFor="let option of options()" [value]="option.id">{{ option.name }}</option>
            </select>
          </label>
          <label class="block text-xs text-slate-300">
            Modelo
            <select
              class="mt-1 w-56 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              [value]="model()"
              (change)="model.set($any($event.target).value)"
            >
              <option value="">Padrão da chave{{ defaultModel() ? " (" + defaultModel() + ")" : "" }}</option>
              <option *ngFor="let name of models()" [value]="name">{{ name }}</option>
            </select>
          </label>
          <button
            type="button"
            (click)="save()"
            [disabled]="loading().saveAssistantLlm"
            class="rounded-full bg-indigo-500 px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {{ loading().saveAssistantLlm ? "Gravando..." : "Gravar modelo" }}
          </button>
          <p class="w-full text-xs text-slate-500">
            Trocar a chave ou o modelo muda as respostas deste assistente: a comparação com a linha de
            base da avaliação deixa de valer.
          </p>
        </div>
      </ng-container>
      <ng-template #loadingLlm>
        <p class="mt-1 text-sm text-slate-500">Carregando...</p>
      </ng-template>
    </article>
  `
})
export class AssistantLlmSettingsComponent {
  private readonly store = inject(Store);

  readonly assistantId = input.required<string>();

  private readonly llmById = this.store.selectSignal(selectAssistantLlmById);
  protected readonly options = this.store.selectSignal(selectLlmOptions);
  protected readonly defaultOption = this.store.selectSignal(selectDefaultLlmOption);
  protected readonly loading = this.store.selectSignal(selectLlmLoading);
  private readonly menu = this.store.selectSignal(selectMenu);

  protected readonly canEdit = computed(() => this.menu().configureLlm);
  protected readonly llm = computed(() => this.llmById()[this.assistantId()] ?? null);

  /** Rascunho: ``""`` = padrao. */
  protected readonly credentialId = signal("");
  protected readonly model = signal("");

  private readonly selectedOption = computed(() => {
    const id = this.credentialId();
    return id ? this.options().find((item) => item.id === id) ?? null : this.defaultOption();
  });
  protected readonly models = computed(() => this.selectedOption()?.models ?? []);
  protected readonly defaultModel = computed(() => this.selectedOption()?.default_model ?? "");

  protected readonly providerLabel = providerLabel;
  protected readonly sourceLabel = llmSourceLabel;

  constructor() {
    effect(() => {
      const assistantId = this.assistantId();
      untracked(() => {
        this.store.dispatch(llmConfigActions.loadAssistantLlm({ assistantId }));
        if (this.canEdit()) {
          this.store.dispatch(llmConfigActions.loadOptions());
        }
      });
    });
    // O rascunho acompanha o que esta gravado sempre que chega do servidor.
    effect(() => {
      const current = this.llm();
      untracked(() => {
        this.credentialId.set(current?.credential_id ?? "");
        this.model.set(current?.model ?? "");
      });
    });
  }

  protected onCredentialChange(credentialId: string): void {
    this.credentialId.set(credentialId);
    // O modelo escolhido pode nao existir na outra chave.
    if (this.model() && !this.models().includes(this.model())) {
      this.model.set("");
    }
  }

  protected save(): void {
    if (this.loading().saveAssistantLlm) {
      return;
    }
    this.store.dispatch(
      llmConfigActions.saveAssistantLlm({
        assistantId: this.assistantId(),
        input: { credential_id: this.credentialId() || null, model: this.model() || null }
      })
    );
  }
}
