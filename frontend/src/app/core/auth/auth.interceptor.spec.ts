/**
 * FE-03: interceptor e guard com o Angular real (injecao), sem TestBed.
 * As regras puras (URLs, mensagens) tem spec proprio em ``http-auth.spec.ts``
 * e ``access.spec.ts``.
 */
import { HttpErrorResponse, HttpEvent, HttpHandlerFn, HttpRequest, HttpResponse } from "@angular/common/http";
import { Injector, runInInjectionContext } from "@angular/core";
import { Router, UrlTree } from "@angular/router";
import { Store } from "@ngrx/store";
import { Observable, firstValueFrom, of, throwError } from "rxjs";
import { describe, expect, it, vi } from "vitest";

import { initialAuthState } from "../../store/auth.reducer";
import { authInterceptor } from "./auth.interceptor";
import { roleGuard } from "./auth.guard";
import { Roles, SessionUser } from "./auth.models";
import { AuthService } from "./auth.service";
import { FORBIDDEN_MESSAGE } from "./http-auth";

function fakeAuth(token: string | null = "tok-123") {
  return {
    validAccessToken: vi.fn(async () => token),
    expire: vi.fn(),
    login: vi.fn(async () => undefined)
  };
}

function runInterceptor(
  auth: ReturnType<typeof fakeAuth>,
  request: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> {
  const injector = Injector.create({ providers: [{ provide: AuthService, useValue: auth }] });
  return runInInjectionContext(injector, () => authInterceptor(request, next));
}

const ok: HttpHandlerFn = () => of(new HttpResponse({ status: 200 }));

describe("authInterceptor (RF-46)", () => {
  it("anexa o Bearer apenas as chamadas da API", async () => {
    const auth = fakeAuth();
    const seen: HttpRequest<unknown>[] = [];
    const next: HttpHandlerFn = (request) => {
      seen.push(request);
      return ok(request);
    };

    await firstValueFrom(runInterceptor(auth, new HttpRequest("GET", "/api/assistants"), next));
    await firstValueFrom(runInterceptor(auth, new HttpRequest("GET", "/config.json"), next));
    await firstValueFrom(
      runInterceptor(auth, new HttpRequest("GET", "https://evil.example/api/assistants"), next)
    );

    expect(seen[0].headers.get("Authorization")).toBe("Bearer tok-123");
    expect(seen[1].headers.has("Authorization")).toBe(false);
    expect(seen[2].headers.has("Authorization")).toBe(false);
    expect(auth.validAccessToken).toHaveBeenCalledTimes(1);
  });

  it("segue sem cabecalho quando nao ha token", async () => {
    const auth = fakeAuth(null);
    let sent: HttpRequest<unknown> | undefined;
    await firstValueFrom(
      runInterceptor(auth, new HttpRequest("GET", "/api/assistants"), (request) => {
        sent = request;
        return ok(request);
      })
    );
    expect(sent!.headers.has("Authorization")).toBe(false);
  });

  it("401 encerra a sessao, menos na leitura da propria sessao (/me)", async () => {
    const unauthorized: HttpHandlerFn = () =>
      throwError(() => new HttpErrorResponse({ status: 401 }));

    const auth = fakeAuth();
    await expect(
      firstValueFrom(runInterceptor(auth, new HttpRequest("GET", "/api/assistants"), unauthorized))
    ).rejects.toBeInstanceOf(HttpErrorResponse);
    expect(auth.expire).toHaveBeenCalledTimes(1);

    const sessionRead = fakeAuth();
    await expect(
      firstValueFrom(runInterceptor(sessionRead, new HttpRequest("GET", "/api/me"), unauthorized))
    ).rejects.toBeInstanceOf(HttpErrorResponse);
    expect(sessionRead.expire).not.toHaveBeenCalled();
  });

  it("403 vira mensagem legivel e nao encerra a sessao", async () => {
    const auth = fakeAuth();
    const forbidden: HttpHandlerFn = () =>
      throwError(() => new HttpErrorResponse({ status: 403, error: { detail: "forbidden" } }));

    const error = await firstValueFrom(
      runInterceptor(auth, new HttpRequest("GET", "/api/admin/usage"), forbidden)
    ).catch((value: HttpErrorResponse) => value);

    expect(error.status).toBe(403);
    expect(error.error.detail).toBe(FORBIDDEN_MESSAGE);
    expect(auth.expire).not.toHaveBeenCalled();
  });

  it("outros erros passam sem alteracao", async () => {
    const auth = fakeAuth();
    const original = new HttpErrorResponse({ status: 503 });
    const error = await firstValueFrom(
      runInterceptor(auth, new HttpRequest("GET", "/api/groups"), () => throwError(() => original))
    ).catch((value: unknown) => value);
    expect(error).toBe(original);
    expect(auth.expire).not.toHaveBeenCalled();
  });
});

const user = (...roles: string[]): SessionUser => ({ id: "u1", name: "U", roles, groups: [] });

function runGuard(
  session: { status: string; user: SessionUser | null },
  roles: Parameters<typeof roleGuard>
) {
  const auth = fakeAuth();
  const tree = { redirectedTo: "/chat" } as unknown as UrlTree;
  const router = { createUrlTree: vi.fn(() => tree) };
  const store = {
    select: () => of({ ...initialAuthState, ...session })
  };
  const injector = Injector.create({
    providers: [
      { provide: Store, useValue: store },
      { provide: Router, useValue: router },
      { provide: AuthService, useValue: auth }
    ]
  });
  const result = runInInjectionContext(injector, () =>
    roleGuard(...roles)({} as never, {} as never)
  ) as Observable<boolean | UrlTree>;
  return { result: firstValueFrom(result), auth, router, tree };
}

describe("roleGuard (CT-32)", () => {
  it("libera quem tem o papel exigido", async () => {
    const { result } = runGuard({ status: "authenticated", user: user(Roles.admin) }, [Roles.admin]);
    expect(await result).toBe(true);
  });

  it("manda para o chat quem esta autenticado sem o papel", async () => {
    const { result, router, tree } = runGuard(
      { status: "authenticated", user: user(Roles.user) },
      [Roles.admin]
    );
    expect(await result).toBe(tree);
    expect(router.createUrlTree).toHaveBeenCalledWith(["/chat"]);
  });

  it("inicia o login quando nao ha sessao", async () => {
    const { result, auth } = runGuard({ status: "anonymous", user: null }, [Roles.user]);
    expect(await result).toBe(false);
    expect(auth.login).toHaveBeenCalledTimes(1);
  });

  it("bloqueia sem iniciar login quando a sessao deu erro", async () => {
    const { result, auth } = runGuard({ status: "error", user: null }, []);
    expect(await result).toBe(false);
    expect(auth.login).not.toHaveBeenCalled();
  });

  it("sem papeis exigidos basta estar autenticado", async () => {
    const { result } = runGuard({ status: "authenticated", user: user() }, []);
    expect(await result).toBe(true);
  });
});
