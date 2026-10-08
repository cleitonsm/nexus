import { CommonModule } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { Store } from "@ngrx/store";

import { Conversation } from "../shared/models/nexus.models";
import { nexusActions } from "../store/nexus.actions";
import {
  selectArchivedConversationDetail,
  selectArchivedConversations,
  selectAssistants,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

/**
 * Conversas anteriores a autenticacao, sem dono (decisao PC-D5). So o
 * administrador lista, le e exclui; cada acao entra na trilha de auditoria.
 */
@Component({
  selector: "app-archived-conversations-page",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./archived-conversations-page.component.html",
  host: { class: "flex-1 min-h-0 overflow-y-auto p-4 lg:p-6" }
})
export class ArchivedConversationsPageComponent {
  private readonly store = inject(Store);

  protected readonly conversations = this.store.selectSignal(selectArchivedConversations);
  protected readonly detail = this.store.selectSignal(selectArchivedConversationDetail);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  private readonly assistants = this.store.selectSignal(selectAssistants);

  /** Conversa cuja exclusao aguarda confirmacao. */
  protected readonly confirmingDelete = signal<string | null>(null);

  private readonly assistantNames = computed(
    () => new Map(this.assistants().map((assistant) => [assistant.id, assistant.name]))
  );

  constructor() {
    this.store.dispatch(nexusActions.closeArchivedConversation());
    this.store.dispatch(nexusActions.loadArchivedConversations());
  }

  protected assistantName(assistantId: string): string {
    return this.assistantNames().get(assistantId) ?? assistantId;
  }

  protected title(conversation: Conversation): string {
    return conversation.name?.trim() || "Conversa sem título";
  }

  protected open(conversation: Conversation): void {
    this.store.dispatch(
      nexusActions.openArchivedConversation({ conversationId: conversation.id })
    );
  }

  protected close(): void {
    this.store.dispatch(nexusActions.closeArchivedConversation());
  }

  protected askDelete(conversation: Conversation): void {
    this.confirmingDelete.set(conversation.id);
  }

  protected cancelDelete(): void {
    this.confirmingDelete.set(null);
  }

  protected confirmDelete(conversation: Conversation): void {
    this.confirmingDelete.set(null);
    this.store.dispatch(
      nexusActions.deleteArchivedConversation({ conversationId: conversation.id })
    );
  }

  protected roleLabel(role: string): string {
    return role === "user" ? "Pergunta" : role === "assistant" ? "Resposta" : role;
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
