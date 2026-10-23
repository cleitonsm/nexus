import { createFeatureSelector, createSelector } from "@ngrx/store";

import { SessionSnapshot, menuFor } from "../core/auth/access";
import { AuthState, authFeatureKey } from "./auth.reducer";

export const selectAuthState = createFeatureSelector<AuthState>(authFeatureKey);

export const selectSessionStatus = createSelector(selectAuthState, (state) => state.status);

export const selectSessionUser = createSelector(selectAuthState, (state) => state.user);

export const selectSessionError = createSelector(selectAuthState, (state) => state.error);

export const selectSessionSnapshot = createSelector(
  selectAuthState,
  (state): SessionSnapshot => ({ status: state.status, user: state.user })
);

/** Itens de menu e acoes visiveis para o papel do usuario (RF-46). */
export const selectMenu = createSelector(selectSessionUser, (user) => menuFor(user));
