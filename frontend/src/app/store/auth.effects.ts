import { inject } from "@angular/core";
import { Actions, createEffect, ofType } from "@ngrx/effects";
import { catchError, map, of, switchMap, tap } from "rxjs";

import { AuthService } from "../core/auth/auth.service";
import { NexusApiService } from "../core/services/nexus-api.service";
import { authActions } from "./auth.actions";

export const loadSessionEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(authActions.loadSession),
      switchMap(() =>
        api.getMe().pipe(
          map((user) => authActions.loadSessionSuccess({ user })),
          catchError((error: unknown) =>
            of(authActions.loadSessionFailure({ error: sessionError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

function sessionError(error: unknown): string {
  const status = (error as { status?: number } | null)?.status;
  if (status === 401) {
    return (
      "A API não aceitou o token emitido pelo Keycloak. " +
      "Confira KEYCLOAK_URL, KEYCLOAK_REALM e OIDC_AUDIENCE no ambiente."
    );
  }
  return "Não foi possível carregar os dados da sua sessão.";
}

export const sessionExpiredEffect = createEffect(
  (actions$ = inject(Actions), auth = inject(AuthService)) =>
    actions$.pipe(
      ofType(authActions.sessionExpired),
      tap(() => void auth.login())
    ),
  { functional: true, dispatch: false }
);

export const logoutEffect = createEffect(
  (actions$ = inject(Actions), auth = inject(AuthService)) =>
    actions$.pipe(
      ofType(authActions.logout),
      tap(() => auth.logout())
    ),
  { functional: true, dispatch: false }
);

export const authEffects = {
  loadSessionEffect,
  sessionExpiredEffect,
  logoutEffect
};
