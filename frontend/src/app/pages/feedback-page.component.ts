import { CommonModule } from "@angular/common";
import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Store } from "@ngrx/store";

import { MessageFeedback } from "../shared/models/nexus.models";
import { nexusActions } from "../store/nexus.actions";
import {
  selectAssistants,
  selectCuratorFeedback,
  selectError,
  selectLoadingState,
  selectNotice
} from "../store/nexus.selectors";

/** Nomes de documentos separados por virgula, sem repeticao. */
function splitNames(text: string): string[] {
  const names = text
    .split(",")
    .map((name) => name.trim())
    .filter((name) => name.length > 0);
  return [...new Set(names)];
}

/** Rascunho da revisao de uma avaliacao, editado no cartao. */
interface ReviewDraft {
  expectedAnswer: string;
  sourceDocuments: string;
  outOfScope: boolean;
}

/**
 * Avaliacoes "nao util" para o curador (RN-33): validar transforma a pergunta
 * em item do conjunto de referencia da SPEC-001; descartar a tira da fila.
 */
@Component({
  selector: "app-feedback-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./feedback-page.component.html",
  host: { class: "flex-1 min-h-0 overflow-y-auto p-4 lg:p-6" }
})
export class FeedbackPageComponent {
  private readonly store = inject(Store);

  protected readonly items = this.store.selectSignal(selectCuratorFeedback);
  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly notice = this.store.selectSignal(selectNotice);
  protected readonly drafts = signal<Record<string, ReviewDraft>>({});
  protected assistantId = "";
  protected status = "pendente";

  constructor() {
    this.load();
  }

  protected load(): void {
    this.store.dispatch(
      nexusActions.loadCuratorFeedback({
        status: this.status,
        assistantId: this.assistantId || null
      })
    );
  }

  protected draftOf(item: MessageFeedback): ReviewDraft {
    return (
      this.drafts()[item.id] ?? {
        expectedAnswer: "",
        sourceDocuments: (item.cited_documents ?? []).join(", "),
        outOfScope: false
      }
    );
  }

  protected updateDraft(item: MessageFeedback, change: Partial<ReviewDraft>): void {
    this.drafts.update((current) => ({
      ...current,
      [item.id]: { ...this.draftOf(item), ...change }
    }));
  }

  /** Dentro do escopo exige resposta esperada e documentos; fora, nao. */
  protected canValidate(item: MessageFeedback): boolean {
    const draft = this.draftOf(item);
    return (
      draft.outOfScope ||
      (draft.expectedAnswer.trim().length > 0 && splitNames(draft.sourceDocuments).length > 0)
    );
  }

  protected validate(item: MessageFeedback): void {
    if (!this.canValidate(item)) {
      return;
    }
    const draft = this.draftOf(item);
    this.store.dispatch(
      nexusActions.reviewFeedback({
        feedbackId: item.id,
        review: {
          decision: "validado",
          expected_answer: draft.outOfScope ? null : draft.expectedAnswer.trim(),
          source_documents: draft.outOfScope ? [] : splitNames(draft.sourceDocuments),
          out_of_scope: draft.outOfScope
        }
      })
    );
  }

  protected discard(item: MessageFeedback): void {
    this.store.dispatch(
      nexusActions.reviewFeedback({ feedbackId: item.id, review: { decision: "descartado" } })
    );
  }

  protected exportValidated(): void {
    if (!this.assistantId) {
      return;
    }
    this.store.dispatch(nexusActions.exportFeedback({ assistantId: this.assistantId }));
  }

  protected assistantName(assistantId: string): string {
    return this.assistants().find((item) => item.id === assistantId)?.name ?? assistantId;
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
