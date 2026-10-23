import { inject, isDevMode, provideAppInitializer } from "@angular/core";
import { bootstrapApplication } from "@angular/platform-browser";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { provideStore } from "@ngrx/store";
import { provideEffects } from "@ngrx/effects";
import { provideStoreDevtools } from "@ngrx/store-devtools";
import { provideRouter } from "@angular/router";

import { AppComponent } from "./app/app.component";
import { appRoutes } from "./app/app.routes";
import { authInterceptor } from "./app/core/auth/auth.interceptor";
import { AuthService } from "./app/core/auth/auth.service";
import { authEffects } from "./app/store/auth.effects";
import { authFeatureKey, authReducer } from "./app/store/auth.reducer";
import { nexusEffects } from "./app/store/nexus.effects";
import { nexusFeatureKey, nexusReducer } from "./app/store/nexus.reducer";

bootstrapApplication(AppComponent, {
  providers: [
    provideHttpClient(withInterceptors([authInterceptor])),
    provideRouter(appRoutes),
    provideStore({ [nexusFeatureKey]: nexusReducer, [authFeatureKey]: authReducer }),
    provideEffects(nexusEffects, authEffects),
    provideStoreDevtools({
      maxAge: 25,
      logOnly: !isDevMode()
    }),
    // Antes de qualquer tela: conclui o login ou leva ao Keycloak (RF-46).
    provideAppInitializer(() => inject(AuthService).initialize())
  ]
}).catch((error: unknown) => {
  console.error("Erro ao iniciar o frontend Nexus.", error);
});
