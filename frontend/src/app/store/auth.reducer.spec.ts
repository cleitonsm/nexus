import "@angular/compiler";
import { describe, expect, it } from "vitest";

import { Roles, SessionUser } from "../core/auth/auth.models";
import { authActions } from "./auth.actions";
import { AuthState, authFeatureKey, authReducer, initialAuthState } from "./auth.reducer";
import {
  selectMenu,
  selectSessionSnapshot,
  selectSessionStatus,
  selectSessionUser
} from "./auth.selectors";

const curator: SessionUser = {
  id: "u1",
  name: "Carla Curadora",
  roles: [Roles.curator],
  groups: ["rh"]
};

const root = (state: AuthState) => ({ [authFeatureKey]: state });

describe("authReducer", () => {
  it("starts loading, without user", () => {
    expect(initialAuthState).toEqual({ status: "loading", user: null, error: null });
  });

  it("stores user, roles and groups when the session is loaded", () => {
    const state = authReducer(initialAuthState, authActions.loadSessionSuccess({ user: curator }));
    expect(state.status).toBe("authenticated");
    expect(selectSessionUser(root(state))).toEqual(curator);
    expect(selectSessionSnapshot(root(state))).toEqual({ status: "authenticated", user: curator });
  });

  it("derives the menu from the roles of the user", () => {
    const state = authReducer(initialAuthState, authActions.loadSessionSuccess({ user: curator }));
    expect(selectMenu(root(state))).toEqual({
      manageAssistants: false,
      manageDocuments: true,
      configureLlm: false,
      viewAudit: false,
      viewUsage: false,
      reviewFeedback: true,
      viewArchived: false
    });
    expect(selectMenu(root(initialAuthState)).manageDocuments).toBe(false);
  });

  it("drops the user when the session expires or the user logs out", () => {
    const loaded = authReducer(initialAuthState, authActions.loadSessionSuccess({ user: curator }));
    for (const action of [authActions.sessionExpired(), authActions.logout()]) {
      const state = authReducer(loaded, action);
      expect(state).toEqual({ status: "anonymous", user: null, error: null });
    }
  });

  it("keeps the reason when the login or the session load fails", () => {
    const failed = authReducer(initialAuthState, authActions.loginFailed({ error: "recusado" }));
    expect(failed).toEqual({ status: "error", user: null, error: "recusado" });
    const loadFailed = authReducer(
      initialAuthState,
      authActions.loadSessionFailure({ error: "sem sessão" })
    );
    expect(selectSessionStatus(root(loadFailed))).toBe("error");
  });

  it("clears a previous error when the session is loaded again", () => {
    const failed = authReducer(initialAuthState, authActions.loginFailed({ error: "x" }));
    expect(authReducer(failed, authActions.loadSession())).toEqual({
      status: "loading",
      user: null,
      error: null
    });
  });
});
