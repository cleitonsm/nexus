import { HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { catchError, from, switchMap, throwError } from "rxjs";

import { AuthService } from "./auth.service";
import {
  FORBIDDEN_MESSAGE,
  bearer,
  endsSessionOnUnauthorized,
  isApiRequest
} from "./http-auth";

/**
 * Anexa o token as chamadas da API e trata as recusas (RF-46):
 * 401 encerra a sessao e volta ao login; 403 vira uma mensagem legivel.
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (!isApiRequest(request.url)) {
    return next(request);
  }
  const auth = inject(AuthService);
  return from(auth.validAccessToken()).pipe(
    switchMap((token) =>
      next(token ? request.clone({ setHeaders: { Authorization: bearer(token) } }) : request)
    ),
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        endsSessionOnUnauthorized(request.url)
      ) {
        auth.expire();
      }
      if (error instanceof HttpErrorResponse && error.status === 403) {
        return throwError(
          () =>
            new HttpErrorResponse({
              error: { detail: FORBIDDEN_MESSAGE },
              status: error.status,
              statusText: error.statusText,
              url: error.url ?? undefined
            })
        );
      }
      return throwError(() => error);
    })
  );
};
