import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, input, signal, untracked } from "@angular/core";
import { Store } from "@ngrx/store";

import {
  EMPTY_RETRIEVAL_INPUT,
  RetrievalDraft,
  retrievalDraftFrom,
  retrievalInputFrom
} from "../../shared/llm/llm-config";
import { RetrievalOrigin } from "../../shared/models/nexus.models";
import { llmConfigActions } from "../../store/llm-config.actions";
import {
  selectAssistantRetrievalById,
  selectLlmLoading
} from "../../store/llm-config.selectors";

const EMPTY_DRAFT: RetrievalDraft = { hybrid: "", candidates: "", topK: "", minScore: "" };

/**
 * "Recuperacao" do assistente (SPEC-013, RF-91, RF-92): busca hibrida,
 * candidatos, top k e nota minima, com o valor efetivo e a origem. Campo vazio
 * segue o padrao do ambiente. O reranker e os filtros de seguranca nao sao
 * configuraveis (D2, D3). Administrador e curador do assistente editam (D7).
 */
@Component({
  selector: "app-assistant-retrieval-settings",
  standalone: true,
  imports: [CommonModule],
  template: `
    <article class="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
      <h2 class="text-lg font-semibold">Recuperação</h2>
      <p class="mt-1 text-sm text-slate-400">
        Como os trechos são buscados antes de chegar ao LLM. Campo vazio segue o padrão do ambiente.
        Vale a partir da próxima pergunta, sem reindexar.
      </p>
      <p class="mt-2 rounded-2xl border border-sky-400/40 bg-sky-500/10 px-4 py-2 text-xs text-sky-100">
        Sempre aplicados, não configuráveis: só voltam trechos dos grupos de quem pergunta e de
        documentos ativos. O reranker sempre ordena os trechos e decide a nota mínima.
      </p>

      <ng-container *ngIf="retrieval() as current; else loadingRetrieval">
        <p
          *ngIf="current.top_k_clamped"
          class="mt-2 rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100"
        >
          O top k gravado passa dos candidatos atuais: as perguntas usam top k = candidatos.
        </p>
        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          <label class="block text-xs text-slate-300">
            Busca híbrida (semântica + palavras exatas)
            <select
              class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              [value]="draft().hybrid"
              (change)="update('hybrid', $any($event.target).value)"
            >
              <option value="">Padrão</option>
              <option value="on">Ligada</option>
              <option value="off">Desligada (só semântica)</option>
            </select>
            <span class="mt-1 block text-slate-500">
              Em uso: {{ current.hybrid_enabled.effective ? "ligada" : "desligada" }}
              ({{ originLabel(current.hybrid_enabled.origin) }})
            </span>
          </label>
          <label class="block text-xs text-slate-300">
            Candidatos ({{ current.limits.candidates[0] }} a {{ current.limits.candidates[1] }})
            <input
              inputmode="numeric"
              class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              [value]="draft().candidates"
              [placeholder]="'padrão'"
              (input)="update('candidates', $any($event.target).value)"
            />
            <span class="mt-1 block text-slate-500">
              Trechos buscados antes do reranker. Em uso: {{ current.candidates.effective }}
              ({{ originLabel(current.candidates.origin) }})
            </span>
          </label>
          <label class="block text-xs text-slate-300">
            Top k ({{ current.limits.top_k[0] }} a {{ current.limits.top_k[1] }}, até os candidatos)
            <input
              inputmode="numeric"
              class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              [value]="draft().topK"
              [placeholder]="'padrão'"
              (input)="update('topK', $any($event.target).value)"
            />
            <span class="mt-1 block text-slate-500">
              Trechos enviados ao LLM. Em uso: {{ current.top_k.effective }}
              ({{ originLabel(current.top_k.origin) }})
            </span>
          </label>
          <label class="block text-xs text-slate-300">
            Nota mínima ({{ current.limits.min_score[0] }} a {{ current.limits.min_score[1] }})
            <input
              inputmode="decimal"
              class="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              [value]="draft().minScore"
              [placeholder]="'padrão'"
              (input)="update('minScore', $any($event.target).value)"
            />
            <span class="mt-1 block text-slate-500">
              Abaixo dela, a resposta é "não encontrei". Em uso: {{ current.min_score.effective }}
              ({{ originLabel(current.min_score.origin) }})
            </span>
          </label>
        </div>
        <p class="mt-3 text-xs text-amber-200">
          Mudar a nota mínima sem medir pode aumentar respostas sem base ou recusas. Calibre com
          scripts/calibrate antes. Qualquer mudança aqui invalida a comparação com a linha de base.
        </p>
        <ul *ngIf="errors().length" class="mt-2 space-y-1 text-xs text-rose-300">
          <li *ngFor="let message of errors()">{{ message }}</li>
        </ul>
        <div class="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            (click)="save()"
            [disabled]="loading().saveAssistantRetrieval"
            class="rounded-full bg-indigo-500 px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {{ loading().saveAssistantRetrieval ? "Gravando..." : "Gravar recuperação" }}
          </button>
          <button
            type="button"
            (click)="restoreDefaults()"
            [disabled]="loading().saveAssistantRetrieval"
            class="rounded-full border border-slate-700 px-5 py-2 text-sm disabled:opacity-50"
          >
            Restaurar padrão
          </button>
        </div>
      </ng-container>
      <ng-template #loadingRetrieval>
        <p class="mt-2 text-sm text-slate-500">Carregando...</p>
      </ng-template>
    </article>
  `
})
export class AssistantRetrievalSettingsComponent {
  private readonly store = inject(Store);

  readonly assistantId = input.required<string>();

  private readonly retrievalById = this.store.selectSignal(selectAssistantRetrievalById);
  protected readonly loading = this.store.selectSignal(selectLlmLoading);
  protected readonly retrieval = computed(
    () => this.retrievalById()[this.assistantId()] ?? null
  );

  protected readonly draft = signal<RetrievalDraft>({ ...EMPTY_DRAFT });
  protected readonly errors = signal<string[]>([]);

  constructor() {
    effect(() => {
      const assistantId = this.assistantId();
      untracked(() =>
        this.store.dispatch(llmConfigActions.loadAssistantRetrieval({ assistantId }))
      );
    });
    effect(() => {
      const current = this.retrieval();
      untracked(() => {
        this.draft.set(current ? retrievalDraftFrom(current) : { ...EMPTY_DRAFT });
        this.errors.set([]);
      });
    });
  }

  protected originLabel(origin: RetrievalOrigin): string {
    return origin === "assistant" ? "deste assistente" : "padrão";
  }

  protected update(field: keyof RetrievalDraft, value: string): void {
    this.draft.update((draft) => ({ ...draft, [field]: value }));
  }

  protected save(): void {
    const current = this.retrieval();
    if (!current || this.loading().saveAssistantRetrieval) {
      return;
    }
    const { input: body, errors } = retrievalInputFrom(this.draft(), current);
    this.errors.set(errors);
    if (errors.length) {
      return;
    }
    this.store.dispatch(
      llmConfigActions.saveAssistantRetrieval({ assistantId: this.assistantId(), input: body })
    );
  }

  protected restoreDefaults(): void {
    if (this.loading().saveAssistantRetrieval) {
      return;
    }
    this.store.dispatch(
      llmConfigActions.saveAssistantRetrieval({
        assistantId: this.assistantId(),
        input: { ...EMPTY_RETRIEVAL_INPUT }
      })
    );
  }
}
