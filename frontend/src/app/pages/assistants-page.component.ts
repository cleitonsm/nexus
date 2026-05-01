import { CommonModule } from "@angular/common";
import { Component, computed, inject } from "@angular/core";
import { Store } from "@ngrx/store";

import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantId,
  selectAssistants,
  selectDocuments,
  selectError
} from "../store/nexus.selectors";

@Component({
  selector: "app-assistants-page",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./assistants-page.component.html"
})
export class AssistantsPageComponent {
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly documents = this.store.selectSignal(selectDocuments);
  protected readonly error = this.store.selectSignal(selectError);

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );
  protected readonly activeAssistantDocuments = computed(() =>
    this.documents().filter((document) => document.assistant_id === this.activeAssistantId())
  );

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
