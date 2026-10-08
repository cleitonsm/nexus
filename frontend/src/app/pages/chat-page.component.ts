import { CommonModule } from "@angular/common";
import { AfterViewChecked, Component, ElementRef, ViewChild, computed, effect, inject, signal } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import { Citation } from "../shared/models/nexus.models";
import { MarkdownPipe } from "../shared/pipes/markdown.pipe";
import { selectMenu } from "../store/auth.selectors";
import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantId,
  selectAssistants,
  selectCurrentCitationsByMessage,
  selectCurrentConversationId,
  selectCurrentMessages,
  selectInferAssistantError,
  selectLoadingState
} from "../store/nexus.selectors";

@Component({
  selector: "app-chat-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MarkdownPipe],
  templateUrl: "./chat-page.component.html",
  host: { class: "flex-1 min-h-0 flex flex-col overflow-hidden" }
})
export class ChatPageComponent implements AfterViewChecked {
  @ViewChild("messagesContainer") private messagesContainer!: ElementRef<HTMLDivElement>;
  @ViewChild("chatTextarea") private chatTextarea!: ElementRef<HTMLTextAreaElement>;

  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  private pendingScroll = false;

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly currentConversationId = this.store.selectSignal(selectCurrentConversationId);
  protected readonly messages = this.store.selectSignal(selectCurrentMessages);
  protected readonly citationsByMessage = this.store.selectSignal(selectCurrentCitationsByMessage);
  /** Fonte aberta no painel: um clique abre, outro clique na mesma fecha. */
  protected readonly openCitation = signal<{ messageId: string; number: number } | null>(null);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  /** So o administrador cria assistentes (RN-21). */
  protected readonly menu = this.store.selectSignal(selectMenu);
  protected readonly isInferring = computed(() => this.loading().inferAssistant);
  protected readonly inferAssistantError = this.store.selectSignal(selectInferAssistantError);
  protected readonly hasAssistants = computed(() => this.assistants().length > 0);
  protected readonly topAssistants = computed(() => this.assistants().slice(0, 3));

  protected readonly hasInteracted = computed(() => this.messages().length > 0 || this.loading().sendChat);

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );

  protected readonly chatForm = this.formBuilder.nonNullable.group({
    question: ["", [Validators.required]]
  });

  ngAfterViewChecked(): void {
    if (this.pendingScroll) {
      const el = this.messagesContainer?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
      this.pendingScroll = false;
    }
  }

  constructor() {
    effect(() => {
      const conversationId = this.currentConversationId();
      if (!conversationId) {
        return;
      }
      this.store.dispatch(nexusActions.loadConversation({ conversationId }));
    });
    effect(() => {
      this.messages();
      this.loading().sendChat;
      this.pendingScroll = true;
    });
  }

  protected onTextareaKeydown(event: KeyboardEvent): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      this.sendQuestion();
    }
  }

  protected autoResize(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    this.resizeTextarea(textarea);
  }

  private resizeTextarea(textarea: HTMLTextAreaElement): void {
    const maxHeight = 262;
    textarea.style.height = "auto";
    const newHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${newHeight}px`;
    if (textarea.scrollHeight > maxHeight) {
      textarea.classList.add("is-overflowing");
    } else {
      textarea.classList.remove("is-overflowing");
    }
  }

  private resetTextareaHeight(): void {
    const textarea = this.chatTextarea?.nativeElement;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.classList.remove("is-overflowing");
    }
  }

  protected sendQuestion(): void {
    if (this.chatForm.invalid) {
      this.chatForm.markAllAsTouched();
      return;
    }
    const conversationId = this.currentConversationId();
    const assistantId = this.activeAssistantId();
    if (!assistantId && this.hasAssistants()) {
      const question = this.chatForm.controls.question.value.trim();
      if (!question) {
        return;
      }
      this.store.dispatch(
        nexusActions.inferAssistantAndSend({
          question,
          topK: 4
        })
      );
      this.chatForm.reset({ question: "" });
      this.resetTextareaHeight();
      return;
    }
    if (!assistantId) {
      return;
    }
    const question = this.chatForm.controls.question.value.trim();
    if (!question) {
      return;
    }

    this.store.dispatch(
      nexusActions.sendChatQuestion({
        assistantId,
        conversationId,
        question,
        topK: 4
      })
    );
    this.chatForm.reset({ question: "" });
    this.resetTextareaHeight();
  }

  protected toggleCitation(messageId: string, citation: Citation): void {
    const current = this.openCitation();
    const isOpen = current?.messageId === messageId && current.number === citation.number;
    this.openCitation.set(isOpen ? null : { messageId, number: citation.number });
  }

  protected isCitationOpen(messageId: string, citation: Citation): boolean {
    const current = this.openCitation();
    return current?.messageId === messageId && current.number === citation.number;
  }

  protected openCitationOf(messageId: string): Citation | null {
    const current = this.openCitation();
    if (current?.messageId !== messageId) {
      return null;
    }
    return (
      this.citationsByMessage()[messageId]?.find((item) => item.number === current.number) ?? null
    );
  }

  protected openCreateAssistantModal(): void {
    if (!this.menu().manageAssistants) {
      return;
    }
    this.store.dispatch(nexusActions.openCreateAssistantModal());
  }

  protected selectAssistantCard(assistantId: string): void {
    this.store.dispatch(nexusActions.selectAssistant({ assistantId }));
  }

  protected dismissInferError(): void {
    this.store.dispatch(nexusActions.clearInferAssistantError());
  }
}
