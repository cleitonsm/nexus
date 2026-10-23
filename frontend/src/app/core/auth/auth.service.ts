import { Injectable, inject } from "@angular/core";
import { Store } from "@ngrx/store";

import { authActions } from "../../store/auth.actions";
import { AuthConfig, TokenSet } from "./auth.models";
import { OidcClient, OidcUnavailableError, safeReturnUrl } from "./oidc-client";

/** Renova o token este tempo antes de expirar. */
const REFRESH_MARGIN_MS = 30_000;
/** Esperas entre as tentativas de renovação quando o Keycloak não responde. */
const REFRESH_RETRY_DELAYS_MS = [1_000, 3_000];
/** Nova tentativa em segundo plano depois que as esperas acabam. */
const REFRESH_BACKGROUND_RETRY_MS = 30_000;
/** Um token com menos que isto de validade e renovado antes de ser usado. */
const MIN_VALIDITY_MS = 10_000;
const CONFIG_URL = "/config.json";

/**
 * Sessao OIDC do frontend (RF-46). Os tokens vivem apenas nesta instancia,
 * em memoria: recarregar a pagina passa de novo pelo Keycloak, que reconhece
 * a sessao aberta e devolve o usuario sem pedir a senha.
 */
@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly store = inject(Store);

  private client: OidcClient | null = null;
  private tokens: TokenSet | null = null;
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;
  private refreshing: Promise<string | null> | null = null;
  private leaving = false;

  /** Executado antes de a aplicacao renderizar: sem sessao, vai ao login. */
  async initialize(): Promise<void> {
    try {
      this.client = new OidcClient(await loadConfig(), {
        fetch: (input, init) => fetch(input, init),
        crypto,
        storage: sessionStorage,
        now: () => Date.now()
      });
      const result = await this.client.completeLogin(
        new URL(window.location.href),
        this.redirectUri()
      );
      if (result) {
        this.setTokens(result.tokens);
        window.history.replaceState(null, "", safeReturnUrl(result.returnUrl));
        this.store.dispatch(authActions.loadSession());
        return;
      }
    } catch (error) {
      // Sem novo redirecionamento automatico: um erro repetido viraria um laco.
      this.store.dispatch(authActions.loginFailed({ error: messageOf(error) }));
      return;
    }
    await this.login();
  }

  /** Leva o navegador ao Keycloak; a promessa nao se resolve nesta pagina. */
  async login(): Promise<void> {
    if (this.leaving || !this.client) {
      return;
    }
    this.leaving = true;
    const returnUrl = `${window.location.pathname}${window.location.search}`;
    try {
      window.location.assign(
        await this.client.authorizationUrl(this.redirectUri(), safeReturnUrl(returnUrl))
      );
    } catch (error) {
      this.leaving = false;
      this.store.dispatch(authActions.loginFailed({ error: messageOf(error) }));
      return;
    }
    await new Promise<never>(() => undefined);
  }

  logout(): void {
    if (this.leaving || !this.client) {
      return;
    }
    this.leaving = true;
    const address = this.client.logoutUrl(this.redirectUri(), this.tokens?.idToken ?? null);
    this.clear();
    window.location.assign(address);
  }

  /** Token de acesso valido para uma chamada a API, renovado se preciso. */
  async validAccessToken(): Promise<string | null> {
    if (!this.tokens) {
      return null;
    }
    if (this.tokens.expiresAt - Date.now() > MIN_VALIDITY_MS) {
      return this.tokens.accessToken;
    }
    return this.refresh();
  }

  /** A API recusou o token: a sessao acabou e o usuario volta ao login. */
  expire(): void {
    if (this.leaving) {
      return;
    }
    this.clear();
    this.store.dispatch(authActions.sessionExpired());
  }

  private refresh(): Promise<string | null> {
    this.refreshing ??= this.renew().finally(() => {
      this.refreshing = null;
    });
    return this.refreshing;
  }

  private async renew(): Promise<string | null> {
    const refreshToken = this.tokens?.refreshToken;
    if (!refreshToken || !this.client) {
      this.expire();
      return null;
    }
    for (let attempt = 0; ; attempt += 1) {
      try {
        this.setTokens(await this.client.refresh(refreshToken));
        return this.tokens?.accessToken ?? null;
      } catch (error) {
        if (!(error instanceof OidcUnavailableError)) {
          // O Keycloak recusou o refresh token (expirado ou revogado): sessão encerrada.
          this.expire();
          return null;
        }
        const delay = REFRESH_RETRY_DELAYS_MS[attempt];
        if (delay === undefined) {
          // Rede ou Keycloak fora do ar: não derruba a sessão; tenta de novo adiante.
          this.scheduleRefresh(REFRESH_BACKGROUND_RETRY_MS);
          return null;
        }
        await new Promise<void>((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  private scheduleRefresh(delay: number): void {
    this.cancelTimer();
    this.refreshTimer = setTimeout(() => void this.refresh(), delay);
  }

  private setTokens(tokens: TokenSet): void {
    this.tokens = tokens;
    this.scheduleRefresh(Math.max(tokens.expiresAt - Date.now() - REFRESH_MARGIN_MS, 0));
  }

  private clear(): void {
    this.tokens = null;
    this.cancelTimer();
  }

  private cancelTimer(): void {
    if (this.refreshTimer !== null) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  private redirectUri(): string {
    return `${window.location.origin}/`;
  }
}

async function loadConfig(): Promise<AuthConfig> {
  const response = await fetch(CONFIG_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Não foi possível carregar a configuração de login.");
  }
  const body = (await response.json()) as Partial<AuthConfig>;
  if (!body.keycloakUrl || !body.realm || !body.clientId) {
    throw new Error("A configuração de login está incompleta.");
  }
  return { keycloakUrl: body.keycloakUrl, realm: body.realm, clientId: body.clientId };
}

function messageOf(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : "Não foi possível concluir o login.";
}
