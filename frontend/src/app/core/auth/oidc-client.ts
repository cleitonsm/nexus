import { AuthConfig, TokenSet } from "./auth.models";
import { codeChallenge, randomString } from "./pkce";

/** O que o cliente precisa do navegador; os testes fornecem dubles. */
export interface OidcEnvironment {
  fetch: (input: string, init?: RequestInit) => Promise<Response>;
  crypto: { getRandomValues: Crypto["getRandomValues"]; subtle: Pick<SubtleCrypto, "digest"> };
  /**
   * Guarda, so durante a ida ao Keycloak, o `state`, o verificador do PKCE e
   * o endereco de retorno. Nunca recebe tokens.
   */
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  now: () => number;
}

export interface LoginResult {
  tokens: TokenSet;
  /** Caminho em que o usuario estava antes de ir ao login. */
  returnUrl: string;
}

interface PendingLogin {
  state: string;
  verifier: string;
  returnUrl: string;
}

interface TokenResponse {
  access_token?: unknown;
  refresh_token?: unknown;
  id_token?: unknown;
  expires_in?: unknown;
}

export const PENDING_LOGIN_KEY = "nexus.oidc.pending";

export class OidcError extends Error {}

/** Authorization Code com PKCE contra o Keycloak (RF-40, RF-46). */
export class OidcClient {
  constructor(
    private readonly config: AuthConfig,
    private readonly environment: OidcEnvironment
  ) {}

  get issuer(): string {
    return `${this.config.keycloakUrl.replace(/\/+$/, "")}/realms/${this.config.realm}`;
  }

  private endpoint(name: "auth" | "token" | "logout"): string {
    return `${this.issuer}/protocol/openid-connect/${name}`;
  }

  /** Prepara a ida ao login e devolve o endereco do Keycloak. */
  async authorizationUrl(redirectUri: string, returnUrl: string): Promise<string> {
    const pending: PendingLogin = {
      state: randomString(32, this.environment.crypto),
      verifier: randomString(64, this.environment.crypto),
      returnUrl
    };
    this.environment.storage.setItem(PENDING_LOGIN_KEY, JSON.stringify(pending));
    const parameters = new URLSearchParams({
      client_id: this.config.clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid",
      state: pending.state,
      code_challenge: await codeChallenge(pending.verifier, this.environment.crypto.subtle),
      code_challenge_method: "S256"
    });
    return `${this.endpoint("auth")}?${parameters.toString()}`;
  }

  /**
   * Conclui o login quando o endereco atual e o retorno do Keycloak.
   * Devolve null quando nao e (nenhum `code` nem `error` na consulta).
   */
  async completeLogin(currentUrl: URL, redirectUri: string): Promise<LoginResult | null> {
    const code = currentUrl.searchParams.get("code");
    const error = currentUrl.searchParams.get("error");
    if (!code && !error) {
      return null;
    }
    const pending = this.takePendingLogin();
    if (error) {
      throw new OidcError(`O login foi recusado pelo Keycloak (${error}).`);
    }
    if (!pending || pending.state !== currentUrl.searchParams.get("state")) {
      throw new OidcError("A resposta do login não corresponde a um pedido desta sessão.");
    }
    const tokens = await this.requestTokens({
      grant_type: "authorization_code",
      code: code ?? "",
      redirect_uri: redirectUri,
      client_id: this.config.clientId,
      code_verifier: pending.verifier
    });
    return { tokens, returnUrl: pending.returnUrl };
  }

  /** Renovacao silenciosa: troca o refresh token por novos tokens. */
  refresh(refreshToken: string): Promise<TokenSet> {
    return this.requestTokens({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: this.config.clientId
    });
  }

  logoutUrl(postLogoutRedirectUri: string, idToken: string | null): string {
    const parameters = new URLSearchParams({
      client_id: this.config.clientId,
      post_logout_redirect_uri: postLogoutRedirectUri
    });
    if (idToken) {
      parameters.set("id_token_hint", idToken);
    }
    return `${this.endpoint("logout")}?${parameters.toString()}`;
  }

  private takePendingLogin(): PendingLogin | null {
    const raw = this.environment.storage.getItem(PENDING_LOGIN_KEY);
    this.environment.storage.removeItem(PENDING_LOGIN_KEY);
    if (!raw) {
      return null;
    }
    try {
      const parsed = JSON.parse(raw) as Partial<PendingLogin>;
      if (
        typeof parsed.state === "string" &&
        typeof parsed.verifier === "string" &&
        typeof parsed.returnUrl === "string"
      ) {
        return { state: parsed.state, verifier: parsed.verifier, returnUrl: parsed.returnUrl };
      }
    } catch {
      // Conteudo invalido equivale a nao haver login pendente.
    }
    return null;
  }

  private async requestTokens(form: Record<string, string>): Promise<TokenSet> {
    const requestedAt = this.environment.now();
    let response: Response;
    try {
      response = await this.environment.fetch(this.endpoint("token"), {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(form).toString()
      });
    } catch {
      throw new OidcError("Não foi possível falar com o Keycloak.");
    }
    if (!response.ok) {
      throw new OidcError(`O Keycloak recusou o pedido de token (HTTP ${response.status}).`);
    }
    const body = (await response.json()) as TokenResponse;
    if (typeof body.access_token !== "string" || typeof body.expires_in !== "number") {
      throw new OidcError("O Keycloak devolveu uma resposta de token inesperada.");
    }
    return {
      accessToken: body.access_token,
      refreshToken: typeof body.refresh_token === "string" ? body.refresh_token : null,
      idToken: typeof body.id_token === "string" ? body.id_token : null,
      expiresAt: requestedAt + body.expires_in * 1000
    };
  }
}

/** Caminho interno seguro para voltar depois do login; qualquer outro vira "/". */
export function safeReturnUrl(candidate: string): string {
  return candidate.startsWith("/") && !candidate.startsWith("//") ? candidate : "/";
}
