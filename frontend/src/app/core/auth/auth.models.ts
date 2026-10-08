/** Papeis de realm do Keycloak reconhecidos pelo Nexus (RF-41). */
export const Roles = {
  admin: "nexus-admin",
  curator: "nexus-curador",
  user: "nexus-usuario"
} as const;

export type Role = (typeof Roles)[keyof typeof Roles];

/** Enderecos publicos do login, servidos em /config.json. */
export interface AuthConfig {
  keycloakUrl: string;
  realm: string;
  clientId: string;
}

/** Identidade devolvida por GET /me: o que a API leu do token. */
export interface SessionUser {
  id: string;
  name: string;
  roles: string[];
  groups: string[];
}

/**
 * Tokens da sessao. Ficam apenas em memoria: nunca em localStorage,
 * sessionStorage ou cookie gravado pelo frontend.
 */
export interface TokenSet {
  accessToken: string;
  refreshToken: string | null;
  idToken: string | null;
  /** Instante, em milissegundos, em que o token de acesso expira. */
  expiresAt: number;
}

export type SessionStatus = "loading" | "authenticated" | "anonymous" | "error";
