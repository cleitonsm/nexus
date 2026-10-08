import { createReducer, on } from "@ngrx/store";

import { SessionStatus, SessionUser } from "../core/auth/auth.models";
import { authActions } from "./auth.actions";

export const authFeatureKey = "auth";

/** Sessao: usuario, papeis, grupos e situacao. Os tokens nao ficam no store. */
export interface AuthState {
  status: SessionStatus;
  user: SessionUser | null;
  error: string | null;
}

export const initialAuthState: AuthState = {
  status: "loading",
  user: null,
  error: null
};

export const authReducer = createReducer(
  initialAuthState,
  on(authActions.loadSession, (state) => ({ ...state, status: "loading" as const, error: null })),
  on(authActions.loadSessionSuccess, (_state, { user }) => ({
    status: "authenticated" as const,
    user,
    error: null
  })),
  on(authActions.loadSessionFailure, authActions.loginFailed, (_state, { error }) => ({
    status: "error" as const,
    user: null,
    error
  })),
  on(authActions.sessionExpired, authActions.logout, () => ({
    status: "anonymous" as const,
    user: null,
    error: null
  }))
);
