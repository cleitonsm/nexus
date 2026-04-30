import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import { nexusActions } from "../store/nexus.actions";
import {
  selectApiKeyStatus,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

@Component({
  selector: "app-admin-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: "./admin-page.component.html"
})
export class AdminPageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly apiKeyStatus = this.store.selectSignal(selectApiKeyStatus);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);

  protected readonly apiKeyForm = this.formBuilder.nonNullable.group({
    apiKey: ["", [Validators.required]]
  });

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
