import { CommonModule } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { Store } from "@ngrx/store";

import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantConversations,
  selectActiveAssistantId,
  selectApiKeyStatus,
  selectAssistants,
  selectCurrentConversationId,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

@Component({
  selector: "app-shell",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: "./shell.component.html"
})
export class ShellComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly conversations = this.store.selectSignal(selectActiveAssistantConversations);
  protected readonly currentConversationId = this.store.selectSignal(selectCurrentConversationId);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly apiKeyStatus = this.store.selectSignal(selectApiKeyStatus);

  protected readonly sidebarCollapsed = signal(false);
  protected readonly mobileSidebarOpen = signal(false);
  protected readonly createAssistantModalOpen = signal(false);
  protected readonly adminModalOpen = signal(false);

  protected readonly sidebarContentVisible = computed(
    () => !this.sidebarCollapsed() || this.mobileSidebarOpen()
  );

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );

  protected readonly assistantForm = this.formBuilder.nonNullable.group({
    name: ["", [Validators.required, Validators.maxLength(80)]],
    description: [""]
  });

  protected readonly apiKeyForm = this.formBuilder.nonNullable.group({
    apiKey: ["", [Validators.required]]
  });

  constructor() {
    this.store.dispatch(nexusActions.loadAssistants());
    this.store.dispatch(nexusActions.loadApiKeyStatus());
  }

  protected toggleNavigation(): void {
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      this.mobileSidebarOpen.update((isOpen) => !isOpen);
      return;
    }
    this.sidebarCollapsed.update((isCollapsed) => !isCollapsed);
  }

  protected closeMobileSidebar(): void {
    this.mobileSidebarOpen.set(false);
  }

  protected openCreateAssistantModal(): void {
    this.createAssistantModalOpen.set(true);
  }

  protected closeCreateAssistantModal(): void {
    this.createAssistantModalOpen.set(false);
    this.assistantForm.reset({ name: "", description: "" });
  }

  protected openAdminModal(): void {
    this.adminModalOpen.set(true);
  }

  protected closeAdminModal(): void {
    this.adminModalOpen.set(false);
    this.apiKeyForm.reset({ apiKey: "" });
  }

  protected selectAssistant(assistantId: string): void {
    this.store.dispatch(nexusActions.selectAssistant({ assistantId }));
  }

  protected createAssistant(): void {
    if (this.assistantForm.invalid || this.loading().createAssistant) {
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
    this.closeCreateAssistantModal();
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

  protected saveApiKey(): void {
    if (this.apiKeyForm.invalid || this.loading().saveApiKey) {
      this.apiKeyForm.markAllAsTouched();
      return;
    }

    this.store.dispatch(
      nexusActions.saveApiKey({
        apiKey: this.apiKeyForm.controls.apiKey.value.trim()
      })
    );
    this.apiKeyForm.reset({ apiKey: "" });
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
