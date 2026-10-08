import { Component, inject } from "@angular/core";
import { RouterOutlet } from "@angular/router";
import { Store } from "@ngrx/store";

import { AuthService } from "./core/auth/auth.service";
import { selectSessionError, selectSessionStatus } from "./store/auth.selectors";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: "./app.component.html"
})
export class AppComponent {
  private readonly store = inject(Store);
  private readonly auth = inject(AuthService);

  protected readonly status = this.store.selectSignal(selectSessionStatus);
  protected readonly error = this.store.selectSignal(selectSessionError);

  protected retryLogin(): void {
    void this.auth.login();
  }
}
