import { inject } from "@angular/core";
import { CanActivateFn, Router, UrlTree } from "@angular/router";
import { Store } from "@ngrx/store";
import { filter, map, take } from "rxjs";

import { selectSessionSnapshot } from "../../store/auth.selectors";
import { decideAccess, resolveNavigation } from "./access";
import { Role } from "./auth.models";
import { AuthService } from "./auth.service";

/**
 * Guard de rota por papel (CT-32). Sem papeis, exige apenas a sessao.
 * Esconde telas; quem autoriza de fato e a API (RNF-23).
 */
export function roleGuard(...roles: Role[]): CanActivateFn {
  return () => {
    const store = inject(Store);
    const router = inject(Router);
    const auth = inject(AuthService);
    return store.select(selectSessionSnapshot).pipe(
      filter((session) => session.status !== "loading"),
      take(1),
      map((session) =>
        resolveNavigation<UrlTree>(decideAccess(session, roles), {
          home: () => router.createUrlTree(["/chat"]),
          login: () => void auth.login()
        })
      )
    );
  };
}
