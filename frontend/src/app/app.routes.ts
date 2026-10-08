import { Routes } from "@angular/router";

import { roleGuard } from "./core/auth/auth.guard";
import { Roles } from "./core/auth/auth.models";
import { AdminPageComponent } from "./pages/admin-page.component";
import { ArchivedConversationsPageComponent } from "./pages/archived-conversations-page.component";
import { AssistantsPageComponent } from "./pages/assistants-page.component";
import { AuditPageComponent } from "./pages/audit-page.component";
import { ChatPageComponent } from "./pages/chat-page.component";
import { FeedbackPageComponent } from "./pages/feedback-page.component";
import { UsagePageComponent } from "./pages/usage-page.component";
import { ShellComponent } from "./shell/shell.component";

export const appRoutes: Routes = [
  {
    path: "",
    component: ShellComponent,
    // Toda rota exige sessao; as administrativas, tambem o papel (RF-46).
    canActivate: [roleGuard()],
    children: [
      { path: "", pathMatch: "full", redirectTo: "chat" },
      { path: "chat", component: ChatPageComponent },
      {
        path: "assistants",
        component: AssistantsPageComponent,
        canActivate: [roleGuard(Roles.admin, Roles.curator)]
      },
      {
        path: "admin",
        component: AdminPageComponent,
        canActivate: [roleGuard(Roles.admin)]
      },
      {
        path: "admin/audit",
        component: AuditPageComponent,
        canActivate: [roleGuard(Roles.admin)]
      },
      {
        path: "admin/archived",
        component: ArchivedConversationsPageComponent,
        canActivate: [roleGuard(Roles.admin)]
      },
      {
        path: "admin/usage",
        component: UsagePageComponent,
        canActivate: [roleGuard(Roles.admin)]
      },
      {
        path: "feedback",
        component: FeedbackPageComponent,
        canActivate: [roleGuard(Roles.admin, Roles.curator)]
      }
    ]
  },
  { path: "**", redirectTo: "chat" }
];
