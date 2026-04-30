import { CommonModule } from "@angular/common";
import { Component, computed, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";
import { Store } from "@ngrx/store";

import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantId,
  selectAssistants,
  selectDocuments,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

@Component({
  selector: "app-assistants-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: "./assistants-page.component.html"
})
export class AssistantsPageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly documents = this.store.selectSignal(selectDocuments);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );
  protected readonly activeAssistantDocuments = computed(() =>
    this.documents().filter((document) => document.assistant_id === this.activeAssistantId())
  );

  protected readonly uploadForm = this.formBuilder.group({
    metadata: [""]
  });

  private selectedFile: File | null = null;

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
        metadata = JSON.parse(metadataRaw) as Record<string, string>;
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

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
