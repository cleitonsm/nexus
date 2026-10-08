import { Role, Roles, SessionStatus, SessionUser } from "./auth.models";

/** O que os guards e o menu precisam saber da sessao. */
export interface SessionSnapshot {
  status: SessionStatus;
  user: SessionUser | null;
}

export type AccessDecision = "allow" | "login" | "forbidden" | "blocked";

export function hasAnyRole(user: SessionUser | null, roles: readonly Role[]): boolean {
  return !!user && roles.some((role) => user.roles.includes(role));
}

/**
 * Decisao de navegacao (CT-32). Sem papeis exigidos, basta estar autenticado.
 * A API repete toda verificacao: o frontend nunca e a unica barreira (RNF-23).
 */
export function decideAccess(
  session: SessionSnapshot,
  requiredRoles: readonly Role[] = []
): AccessDecision {
  if (session.status === "error") {
    return "blocked";
  }
  if (session.status !== "authenticated" || !session.user) {
    return "login";
  }
  if (requiredRoles.length === 0 || hasAnyRole(session.user, requiredRoles)) {
    return "allow";
  }
  return "forbidden";
}

/** Itens de menu e acoes que cada papel enxerga (RF-46, RN-21). */
export interface MenuVisibility {
  /** Criar e excluir assistentes e vincular grupos. */
  manageAssistants: boolean;
  /** Tela de documentos: enviar arquivos e restringir por grupo. */
  manageDocuments: boolean;
  /** Chave de API do LLM. */
  configureLlm: boolean;
  /** Trilha de auditoria. */
  viewAudit: boolean;
  /** Consumo, custo estimado e limites de uso (SPEC-006, RF-57, D3). */
  viewUsage: boolean;
  /** Avaliacoes negativas das respostas (SPEC-006, RN-33). */
  reviewFeedback: boolean;
}

export function menuFor(user: SessionUser | null): MenuVisibility {
  const admin = hasAnyRole(user, [Roles.admin]);
  const curator = hasAnyRole(user, [Roles.curator]);
  return {
    manageAssistants: admin,
    manageDocuments: admin || curator,
    configureLlm: admin,
    viewAudit: admin,
    viewUsage: admin,
    reviewFeedback: admin || curator
  };
}

/** O que o guard faz com a decisao; isolado do Angular para ser testavel. */
export interface NavigationPort<T> {
  /** Arvore de rota para a pagina inicial. */
  home: () => T;
  /** Inicia o login no Keycloak. */
  login: () => void;
}

export function resolveNavigation<T>(decision: AccessDecision, port: NavigationPort<T>): boolean | T {
  switch (decision) {
    case "allow":
      return true;
    case "forbidden":
      return port.home();
    case "login":
      port.login();
      return false;
    case "blocked":
      return false;
  }
}

/** Grupos digitados em um campo de texto, separados por virgula. */
export function parseGroups(text: string): string[] {
  const names = text
    .split(",")
    .map((name) => name.trim().replace(/^\/+/, ""))
    .filter((name) => name.length > 0);
  return [...new Set(names)].sort((left, right) => left.localeCompare(right));
}
