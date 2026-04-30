import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { Store } from "@ngrx/store";

import { nexusActions } from "../store/nexus.actions";
import { selectActiveAssistantId, selectAssistants } from "../store/nexus.selectors";

@Component({
  selector: "app-shell",
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: "./shell.component.html"
})
export class ShellComponent {
  private readonly store = inject(Store);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);

  constructor() {
    this.store.dispatch(nexusActions.loadAssistants());
  }

  protected selectAssistant(assistantId: string): void {
    this.store.dispatch(nexusActions.selectAssistant({ assistantId }));
  }
}
