import { describe, expect, it } from "vitest";

import { AuthConfig } from "./auth.models";
import {
  OidcClient,
  OidcEnvironment,
  OidcError,
  PENDING_LOGIN_KEY,
  safeReturnUrl
} from "./oidc-client";
import { codeChallenge } from "./pkce";

const CONFIG: AuthConfig = {
  keycloakUrl: "http://localhost:8080/",
  realm: "nexus",
  clientId: "nexus-frontend"
};
const REDIRECT = "http://localhost:4200/";
const TOKEN_URL = "http://localhost:8080/realms/nexus/protocol/openid-connect/token";
const NOW = 1_800_000_000_000;

interface Call {
  url: string;
  body: URLSearchParams;
}

function setup(tokenResponse: { status?: number; body?: unknown; fail?: boolean } = {}) {
  const stored = new Map<string, string>();
  const calls: Call[] = [];
  const environment: OidcEnvironment = {
    fetch: async (url, init) => {
      calls.push({ url, body: new URLSearchParams(String(init?.body ?? "")) });
      if (tokenResponse.fail) {
        throw new TypeError("network down");
      }
      return new Response(
        JSON.stringify(
          tokenResponse.body ?? {
            access_token: "access-1",
            refresh_token: "refresh-1",
            id_token: "id-1",
            expires_in: 300
          }
        ),
        { status: tokenResponse.status ?? 200 }
      );
    },
    crypto,
    storage: {
      getItem: (key) => stored.get(key) ?? null,
      setItem: (key, value) => void stored.set(key, value),
      removeItem: (key) => void stored.delete(key)
    },
    now: () => NOW
  };
  return { client: new OidcClient(CONFIG, environment), stored, calls };
}

async function startLogin(context: ReturnType<typeof setup>, returnUrl = "/chat") {
  const url = new URL(await context.client.authorizationUrl(REDIRECT, returnUrl));
  const pending = JSON.parse(context.stored.get(PENDING_LOGIN_KEY) ?? "{}") as {
    state: string;
    verifier: string;
  };
  return { url, pending };
}

function callback(state: string, code = "code-1"): URL {
  return new URL(`${REDIRECT}?state=${state}&code=${code}&session_state=abc`);
}

describe("OidcClient", () => {
  it("builds the authorization request with PKCE and remembers the pending login", async () => {
    const context = setup();
    const { url, pending } = await startLogin(context, "/admin");

    expect(`${url.origin}${url.pathname}`).toBe(
      "http://localhost:8080/realms/nexus/protocol/openid-connect/auth"
    );
    expect(url.searchParams.get("client_id")).toBe("nexus-frontend");
    expect(url.searchParams.get("redirect_uri")).toBe(REDIRECT);
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("scope")).toBe("openid");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("state")).toBe(pending.state);
    expect(url.searchParams.get("code_challenge")).toBe(
      await codeChallenge(pending.verifier, crypto.subtle)
    );
    expect(pending.verifier).toHaveLength(64);
    expect(url.toString()).not.toContain(pending.verifier);
  });

  it("is not a callback when the address has no code and no error", async () => {
    const context = setup();
    expect(await context.client.completeLogin(new URL(`${REDIRECT}chat`), REDIRECT)).toBeNull();
    expect(context.calls).toHaveLength(0);
  });

  it("exchanges the code with the verifier and returns the tokens", async () => {
    const context = setup();
    const { pending } = await startLogin(context, "/chat?x=1");

    const result = await context.client.completeLogin(callback(pending.state), REDIRECT);

    expect(context.calls).toHaveLength(1);
    expect(context.calls[0].url).toBe(TOKEN_URL);
    expect(Object.fromEntries(context.calls[0].body)).toEqual({
      grant_type: "authorization_code",
      code: "code-1",
      redirect_uri: REDIRECT,
      client_id: "nexus-frontend",
      code_verifier: pending.verifier
    });
    expect(result).toEqual({
      tokens: {
        accessToken: "access-1",
        refreshToken: "refresh-1",
        idToken: "id-1",
        expiresAt: NOW + 300_000
      },
      returnUrl: "/chat?x=1"
    });
  });

  it("keeps no token and no pending login in the storage after the callback", async () => {
    const context = setup();
    const { pending } = await startLogin(context);
    await context.client.completeLogin(callback(pending.state), REDIRECT);
    expect(context.stored.size).toBe(0);
  });

  it("rejects a callback whose state was not issued by this session", async () => {
    const context = setup();
    await startLogin(context);
    await expect(
      context.client.completeLogin(callback("forged-state"), REDIRECT)
    ).rejects.toBeInstanceOf(OidcError);
    expect(context.calls).toHaveLength(0);
    expect(context.stored.size).toBe(0);
  });

  it("rejects a callback when no login was pending", async () => {
    const context = setup();
    await expect(
      context.client.completeLogin(callback("any"), REDIRECT)
    ).rejects.toBeInstanceOf(OidcError);
    expect(context.calls).toHaveLength(0);
  });

  it("reports an error returned by Keycloak without calling the token endpoint", async () => {
    const context = setup();
    const { pending } = await startLogin(context);
    const denied = new URL(`${REDIRECT}?error=access_denied&state=${pending.state}`);
    await expect(context.client.completeLogin(denied, REDIRECT)).rejects.toBeInstanceOf(OidcError);
    expect(context.calls).toHaveLength(0);
  });

  it("fails when the token endpoint refuses, is unreachable or answers nonsense", async () => {
    for (const response of [{ status: 400 }, { fail: true }, { body: { access_token: 1 } }]) {
      const context = setup(response);
      const { pending } = await startLogin(context);
      await expect(
        context.client.completeLogin(callback(pending.state), REDIRECT)
      ).rejects.toBeInstanceOf(OidcError);
    }
  });

  it("refreshes the session with the refresh token", async () => {
    const context = setup({
      body: { access_token: "access-2", refresh_token: "refresh-2", expires_in: 60 }
    });
    const tokens = await context.client.refresh("refresh-1");
    expect(Object.fromEntries(context.calls[0].body)).toEqual({
      grant_type: "refresh_token",
      refresh_token: "refresh-1",
      client_id: "nexus-frontend"
    });
    expect(tokens).toEqual({
      accessToken: "access-2",
      refreshToken: "refresh-2",
      idToken: null,
      expiresAt: NOW + 60_000
    });
  });

  it("builds the logout address with the id token hint", () => {
    const url = new URL(setup().client.logoutUrl(REDIRECT, "id-1"));
    expect(url.pathname).toBe("/realms/nexus/protocol/openid-connect/logout");
    expect(url.searchParams.get("post_logout_redirect_uri")).toBe(REDIRECT);
    expect(url.searchParams.get("id_token_hint")).toBe("id-1");
    expect(new URL(setup().client.logoutUrl(REDIRECT, null)).searchParams.has("id_token_hint")).toBe(
      false
    );
  });

  it("only returns to internal paths after the login", () => {
    expect(safeReturnUrl("/admin/audit?x=1")).toBe("/admin/audit?x=1");
    expect(safeReturnUrl("//evil.example")).toBe("/");
    expect(safeReturnUrl("https://evil.example")).toBe("/");
    expect(safeReturnUrl("")).toBe("/");
  });
});
