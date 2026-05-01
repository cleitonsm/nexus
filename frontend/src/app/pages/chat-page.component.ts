import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import { MarkdownPipe } from "../shared/pipes/markdown.pipe";
import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantId,
  selectAssistants,
  selectCurrentConversationId,
  selectCurrentMessages,
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
  protected readonly currentConversationId = this.store.selectSignal(selectCurrentConversationId);
  protected readonly messages = this.store.selectSignal(selectCurrentMessages);
  protected readonly loading = this.store.selectSignal(selectLoadingState);

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
    effect(() => {
      // #region agent log
      this.agentDebugLog("H5,H6", "chat send button state changed", {
        hasCurrentConversation: Boolean(this.currentConversationId()),
        sendChatLoading: this.loading().sendChat,
        formInvalid: this.chatForm.invalid,
        messageCount: this.messages().length
      });
      // #endregion
    });
  }

  protected sendQuestion(): void {
    if (this.chatForm.invalid) {
      // #region agent log
      this.agentDebugLog("H5", "send question blocked by invalid form", {
        hasCurrentConversation: Boolean(this.currentConversationId()),
        sendChatLoading: this.loading().sendChat
      });
      // #endregion
      this.chatForm.markAllAsTouched();
      return;
    }
    const conversationId = this.currentConversationId();
    const assistantId = this.activeAssistantId();
    if (!assistantId) {
      // #region agent log
      this.agentDebugLog("H5", "send question blocked by missing assistant", {
        hasCurrentConversation: Boolean(conversationId),
        sendChatLoading: this.loading().sendChat
      });
      // #endregion
      return;
    }
    const question = this.chatForm.controls.question.value.trim();
    if (!question) {
      // #region agent log
      this.agentDebugLog("H5", "send question blocked by empty question", {
        hasCurrentConversation: true,
        sendChatLoading: this.loading().sendChat
      });
      // #endregion
      return;
    }

    // #region agent log
    this.agentDebugLog("H6,H7,H8,H9", "dispatching chat question", {
      hasCurrentConversation: true,
      questionLength: question.length,
      messageCount: this.messages().length
    });
    // #endregion
    this.store.dispatch(
      nexusActions.sendChatQuestion({
        assistantId,
        conversationId,
        question,
        topK: 4
      })
    );
    this.chatForm.reset({ question: "" });
  }

  private agentDebugLog(hypothesisId: string, message: string, data: object): void {
    fetch("http://127.0.0.1:7657/ingest/1e04e285-e754-4529-87f1-5953edf93f4e", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Debug-Session-Id": "a1f259"
      },
      body: JSON.stringify({
        sessionId: "a1f259",
        runId: "llm-ui-pre-fix",
        hypothesisId,
        location: "frontend/src/app/pages/chat-page.component.ts",
        message,
        data,
        timestamp: Date.now()
      })
    }).catch(() => {});
  }

}
