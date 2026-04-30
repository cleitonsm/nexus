import { isDevMode } from "@angular/core";
import { bootstrapApplication } from "@angular/platform-browser";
import { provideHttpClient } from "@angular/common/http";
import { provideStore } from "@ngrx/store";
import { provideEffects } from "@ngrx/effects";
import { provideStoreDevtools } from "@ngrx/store-devtools";

import { AppComponent } from "./app/app.component";
import { nexusEffects } from "./app/store/nexus.effects";
import { nexusFeatureKey, nexusReducer } from "./app/store/nexus.reducer";

bootstrapApplication(AppComponent, {
  providers: [
    provideHttpClient(),
    provideStore({ [nexusFeatureKey]: nexusReducer }),
    provideEffects(nexusEffects),
    provideStoreDevtools({
      maxAge: 25,
      logOnly: !isDevMode()
    })
  ]
}).catch((error: unknown) => {
  console.error("Erro ao iniciar o frontend Nexus.", error);
});
