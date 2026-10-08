import { createActionGroup, emptyProps, props } from "@ngrx/store";

import { SessionUser } from "../core/auth/auth.models";

export const authActions = createActionGroup({
  source: "Auth",
  events: {
    "Load Session": emptyProps(),
    "Load Session Success": props<{ user: SessionUser }>(),
    "Load Session Failure": props<{ error: string }>(),
    "Login Failed": props<{ error: string }>(),
    "Session Expired": emptyProps(),
    Logout: emptyProps()
  }
});
