import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import { MarkdownPipe } from "../shared/pipes/markdown.pipe";
import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantConversations,
  selectActiveAssistantId,
  selectAssistants,
  selectCurrentConversationId,
  selectCurrentMessages,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

@Component({
  selector: "app-chat-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MarkdownPipe],
  templateUrl: "./chat-page.component.html"
})
export class ChatPageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly conversations = this.store.selectSignal(selectActiveAssistantConversations);
  protected readonly currentConversationId = this.store.selectSignal(selectCurrentConversationId);
  protected readonly messages = this.store.selectSignal(selectCurrentMessages);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );

  protected readonly chatForm = this.formBuilder.nonNullable.group({
    question: ["", [Validators.required]]
  });

  constructor() {
    effect(() => {
      const conversationId = this.currentConversationId();
      if (!conversationId) {
        return;
      }
      this.store.dispatch(nexusActions.loadConversation({ conversationId }));
    });
  }

  protected createConversation(): void {
    const assistantId = this.activeAssistantId();
    if (!assistantId || this.loading().createConversation) {
      return;
    }
    this.store.dispatch(nexusActions.createConversation({ assistantId }));
  }

  protected selectConversation(conversationId: string): void {
    this.store.dispatch(nexusActions.selectConversation({ conversationId }));
  }

  protected sendQuestion(): void {
    if (this.chatForm.invalid) {
      this.chatForm.markAllAsTouched();
      return;
    }
    const conversationId = this.currentConversationId();
    if (!conversationId) {
      return;
    }
    const question = this.chatForm.controls.question.value.trim();
    if (!question) {
      return;
    }

    this.store.dispatch(
      nexusActions.sendChatQuestion({
        conversationId,
        question,
        topK: 4
      })
    );
    this.chatForm.reset({ question: "" });
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
