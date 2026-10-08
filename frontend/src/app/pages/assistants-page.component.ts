import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, signal } from "@angular/core";
import { Store } from "@ngrx/store";

import { parseGroups } from "../core/auth/access";
import { DocumentAccess } from "../shared/models/nexus.models";
import { selectMenu } from "../store/auth.selectors";
import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantId,
  selectActiveDocumentAccess,
  selectAssistants,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

/**
 * Permissoes do assistente (administrador) e restricao de documentos por
 * grupo (curador e administrador). A API repete toda verificacao.
 */
@Component({
  selector: "app-assistants-page",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./assistants-page.component.html",
  host: { class: "flex-1 min-h-0 overflow-y-auto p-4 lg:p-6" }
})
export class AssistantsPageComponent {
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly documents = this.store.selectSignal(selectActiveDocumentAccess);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly menu = this.store.selectSignal(selectMenu);

  protected readonly activeAssistant = computed(
    () => this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );
  protected readonly assistantGroups = computed(() => this.activeAssistant()?.groups ?? []);

  /** Grupos aplicados aos proximos arquivos enviados (D8). */
  protected readonly uploadGroups = signal("");

  /** Texto digitado e ainda nao salvo; a chave e o id do assistente ou do documento. */
  private readonly drafts = signal<Record<string, string>>({});

  constructor() {
    effect(() => {
      const assistantId = this.activeAssistantId();
      if (assistantId) {
        this.store.dispatch(nexusActions.loadDocumentAccess({ assistantId }));
      }
    });
  }

  protected draft(id: string, saved: readonly string[]): string {
    return this.drafts()[id] ?? saved.join(", ");
  }

  protected onDraftInput(id: string, event: Event): void {
    const target = event.target as HTMLInputElement | null;
    this.drafts.update((drafts) => ({ ...drafts, [id]: target?.value ?? "" }));
  }

  protected saveAssistantGroups(): void {
    const assistant = this.activeAssistant();
    if (!assistant || this.loading().assistantGroups) {
      return;
    }
    const groups = parseGroups(this.draft(assistant.id, this.assistantGroups()));
    this.store.dispatch(nexusActions.setAssistantGroups({ assistantId: assistant.id, groups }));
    this.clearDraft(assistant.id);
  }

  protected saveDocumentGroups(document: DocumentAccess): void {
    if (this.loading().documentGroups) {
      return;
    }
    const groups = parseGroups(this.draft(document.id, document.groups));
    this.store.dispatch(nexusActions.setDocumentGroups({ documentId: document.id, groups }));
    this.clearDraft(document.id);
  }

  protected onFilesSelected(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    const assistantId = this.activeAssistantId();
    if (!assistantId) {
      return;
    }
    const groups = parseGroups(this.uploadGroups());
    for (const file of Array.from(target?.files ?? [])) {
      this.store.dispatch(
        nexusActions.uploadDocument({ assistantId, file, metadata: {}, groups })
      );
    }
    if (target) {
      target.value = "";
    }
  }

  protected onUploadGroupsInput(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    this.uploadGroups.set(target?.value ?? "");
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }

  private clearDraft(id: string): void {
    this.drafts.update(({ [id]: _saved, ...rest }) => rest);
  }
}
