import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import { MarkdownPipe } from "./shared/pipes/markdown.pipe";
import { nexusActions } from "./store/nexus.actions";
import {
  selectActiveAssistantId,
  selectAssistants,
  selectConversationsByAssistant,
  selectCurrentConversationId,
  selectCurrentMessages,
  selectDocuments,
  selectError,
  selectLoadingState
} from "./store/nexus.selectors";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MarkdownPipe],
  templateUrl: "./app.component.html"
})
export class AppComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly conversationsByAssistant = this.store.selectSignal(
    selectConversationsByAssistant
  );
  protected readonly currentConversationId = this.store.selectSignal(
    selectCurrentConversationId
  );
  protected readonly messages = this.store.selectSignal(selectCurrentMessages);
  protected readonly documents = this.store.selectSignal(selectDocuments);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );
  protected readonly activeAssistantDocuments = computed(() =>
    this.documents().filter((document) => document.assistant_id === this.activeAssistantId())
  );

  protected readonly assistantForm = this.formBuilder.nonNullable.group({
    name: ["", [Validators.required, Validators.maxLength(80)]],
    description: [""]
  });

  protected readonly uploadForm = this.formBuilder.group({
    metadata: [""]
  });

  protected readonly chatForm = this.formBuilder.nonNullable.group({
    question: ["", [Validators.required]]
  });

  private selectedFile: File | null = null;

  constructor() {
    this.store.dispatch(nexusActions.loadAssistants());

    effect(() => {
      const conversationId = this.currentConversationId();
      if (!conversationId) {
        return;
      }
      this.store.dispatch(nexusActions.loadConversation({ conversationId }));
    });
  }

  protected createAssistant(): void {
    if (this.assistantForm.invalid) {
      this.assistantForm.markAllAsTouched();
      return;
    }
    const value = this.assistantForm.getRawValue();
    this.store.dispatch(
      nexusActions.createAssistant({
        name: value.name.trim(),
        description: value.description.trim() ? value.description.trim() : null
      })
    );
    this.assistantForm.reset({ name: "", description: "" });
  }

  protected selectAssistant(assistantId: string): void {
    this.store.dispatch(nexusActions.selectAssistant({ assistantId }));
    const conversationId = this.conversationsByAssistant()[assistantId];
    if (!conversationId) {
      this.store.dispatch(nexusActions.createConversation({ assistantId }));
    }
  }

  protected onFileSelected(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    this.selectedFile = target?.files?.[0] ?? null;
  }

  protected uploadDocument(): void {
    const assistantId = this.activeAssistantId();
    if (!assistantId || !this.selectedFile) {
      return;
    }

    const metadataRaw = this.uploadForm.controls.metadata.value?.trim() ?? "";
    let metadata: Record<string, string> = {};
    if (metadataRaw) {
      try {
        const parsed = JSON.parse(metadataRaw) as Record<string, string>;
        metadata = parsed;
      } catch {
        this.store.dispatch(
          nexusActions.uploadDocumentFailure({
            error: "Metadata deve estar em JSON válido, por exemplo {\"origem\":\"manual\"}."
          })
        );
        return;
      }
    }

    this.store.dispatch(
      nexusActions.uploadDocument({
        assistantId,
        file: this.selectedFile,
        metadata
      })
    );
    this.uploadForm.reset({ metadata: "" });
    this.selectedFile = null;
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
    const { question } = this.chatForm.getRawValue();
    this.store.dispatch(
      nexusActions.sendChatQuestion({
        conversationId,
        question: question.trim(),
        topK: 4
      })
    );
    this.chatForm.reset({ question: "" });
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
