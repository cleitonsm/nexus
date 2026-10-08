import { CommonModule } from "@angular/common";
import { Component, DestroyRef, computed, effect, inject, signal } from "@angular/core";
import { Store } from "@ngrx/store";

import { parseGroups } from "../core/auth/access";
import {
  canReplace,
  canReprocess,
  formatBytes,
  isInProgress,
  orderWithVersions,
  pendingVersionOf,
  statusLabel
} from "../shared/documents/document-lifecycle";
import { DocumentAccess, DocumentStatus } from "../shared/models/nexus.models";
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
 * Permissoes do assistente (administrador), documentos com seu estado e
 * restricao por grupo (curador e administrador). A API repete toda verificacao.
 *
 * O estado dos documentos e atualizado sem recarregar a pagina enquanto algum
 * estiver pendente ou processando (RNF-33, D4).
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
  private readonly allDocuments = this.store.selectSignal(selectActiveDocumentAccess);
  /** Versao vigente seguida da nova versao em processamento (RN-28). */
  protected readonly documents = computed(() => orderWithVersions(this.allDocuments()));
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

  /** Documento cuja exclusao aguarda confirmacao. */
  protected readonly confirmingDelete = signal<string | null>(null);

  protected readonly statusLabel = statusLabel;
  protected readonly formatBytes = formatBytes;
  protected readonly isInProgress = isInProgress;
  protected readonly canReprocess = canReprocess;

  constructor() {
    effect(() => {
      const assistantId = this.activeAssistantId();
      if (assistantId) {
        this.store.dispatch(nexusActions.loadDocumentAccess({ assistantId }));
      }
    });
    // A consulta periodica so existe com a tela aberta.
    inject(DestroyRef).onDestroy(() =>
      this.store.dispatch(nexusActions.stopDocumentPolling())
    );
  }

  protected canReplace(document: DocumentAccess): boolean {
    return canReplace(document, this.allDocuments());
  }

  protected hasPendingVersion(document: DocumentAccess): boolean {
    return pendingVersionOf(document, this.allDocuments()) !== null;
  }

  protected statusClass(status: DocumentStatus): string {
    switch (status) {
      case "indexado":
        return "bg-emerald-500/15 text-emerald-200";
      case "falhou":
        return "bg-rose-500/15 text-rose-200";
      case "processando":
        return "bg-sky-500/15 text-sky-200 animate-pulse";
      default:
        return "bg-slate-500/20 text-slate-200";
    }
  }

  protected askDelete(document: DocumentAccess): void {
    this.confirmingDelete.set(document.id);
  }

  protected cancelDelete(): void {
    this.confirmingDelete.set(null);
  }

  protected confirmDelete(document: DocumentAccess): void {
    this.confirmingDelete.set(null);
    this.store.dispatch(
      nexusActions.deleteDocument({
        assistantId: document.assistant_id,
        documentId: document.id
      })
    );
  }

  protected reprocess(document: DocumentAccess): void {
    this.store.dispatch(nexusActions.reprocessDocument({ documentId: document.id }));
  }

  protected onReplacementSelected(document: DocumentAccess, event: Event): void {
    const target = event.target as HTMLInputElement | null;
    const file = target?.files?.[0];
    if (file) {
      this.store.dispatch(
        nexusActions.replaceDocument({
          assistantId: document.assistant_id,
          documentId: document.id,
          file
        })
      );
    }
    if (target) {
      target.value = "";
    }
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
