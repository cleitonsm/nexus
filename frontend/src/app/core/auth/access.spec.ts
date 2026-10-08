/** CT-32 (RF-46): o guard leva ao login sem sessao e o menu segue o papel. */
import { describe, expect, it } from "vitest";

import {
  decideAccess,
  menuFor,
  parseGroups,
  resolveNavigation,
  SessionSnapshot
} from "./access";
import { Roles, SessionUser } from "./auth.models";

const user = (...roles: string[]): SessionUser => ({
  id: "u1",
  name: "Usuaria",
  roles,
  groups: ["rh"]
});

const session = (roles: string[] | null): SessionSnapshot =>
  roles === null
    ? { status: "anonymous", user: null }
    : { status: "authenticated", user: user(...roles) };

function navigate(decision: ReturnType<typeof decideAccess>) {
  const calls = { login: 0 };
  const result = resolveNavigation(decision, {
    home: () => "/chat",
    login: () => {
      calls.login += 1;
    }
  });
  return { result, logins: calls.login };
}

describe("decideAccess", () => {
  it("sends a visitor without session to the login", () => {
    expect(decideAccess(session(null))).toBe("login");
    expect(decideAccess(session(null), [Roles.admin])).toBe("login");
    expect(decideAccess({ status: "loading", user: null })).toBe("login");
  });

  it("treats an authenticated status without user as no session", () => {
    expect(decideAccess({ status: "authenticated", user: null })).toBe("login");
  });

  it("allows any authenticated user on routes without required role", () => {
    expect(decideAccess(session([Roles.user]))).toBe("allow");
    expect(decideAccess(session([]))).toBe("allow");
  });

  it("allows a route when the user has one of the required roles", () => {
    expect(decideAccess(session([Roles.curator]), [Roles.admin, Roles.curator])).toBe("allow");
    expect(decideAccess(session([Roles.admin]), [Roles.admin])).toBe("allow");
  });

  it("forbids a route when the user lacks the required role", () => {
    expect(decideAccess(session([Roles.user]), [Roles.admin, Roles.curator])).toBe("forbidden");
    expect(decideAccess(session([Roles.curator]), [Roles.admin])).toBe("forbidden");
    expect(decideAccess(session([]), [Roles.admin])).toBe("forbidden");
  });

  it("blocks navigation when the login failed, without looping to Keycloak", () => {
    expect(decideAccess({ status: "error", user: null })).toBe("blocked");
  });
});

describe("resolveNavigation", () => {
  it("redirects to the Keycloak login without session", () => {
    expect(navigate(decideAccess(session(null)))).toEqual({ result: false, logins: 1 });
  });

  it("lets an allowed navigation through", () => {
    expect(navigate("allow")).toEqual({ result: true, logins: 0 });
  });

  it("sends a forbidden navigation to the home page", () => {
    expect(navigate("forbidden")).toEqual({ result: "/chat", logins: 0 });
  });

  it("stops a blocked navigation without starting a login", () => {
    expect(navigate("blocked")).toEqual({ result: false, logins: 0 });
  });
});

describe("menuFor", () => {
  it("shows every administrative item to the administrator", () => {
    expect(menuFor(user(Roles.admin))).toEqual({
      manageAssistants: true,
      manageDocuments: true,
      configureLlm: true,
      viewAudit: true
    });
  });

  it("shows only document management to the curator", () => {
    expect(menuFor(user(Roles.curator))).toEqual({
      manageAssistants: false,
      manageDocuments: true,
      configureLlm: false,
      viewAudit: false
    });
  });

  it("hides every administrative item from the common user and from no session", () => {
    const hidden = {
      manageAssistants: false,
      manageDocuments: false,
      configureLlm: false,
      viewAudit: false
    };
    expect(menuFor(user(Roles.user))).toEqual(hidden);
    expect(menuFor(user())).toEqual(hidden);
    expect(menuFor(null)).toEqual(hidden);
  });
});

describe("parseGroups", () => {
  it("splits, trims, removes the leading slash, deduplicates and sorts", () => {
    expect(parseGroups(" rh, /financeiro ,rh,, diretoria ")).toEqual([
      "diretoria",
      "financeiro",
      "rh"
    ]);
    expect(parseGroups("  ")).toEqual([]);
  });
});
