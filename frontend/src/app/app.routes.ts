import { Routes } from "@angular/router";

import { AdminPageComponent } from "./pages/admin-page.component";
import { ChatPageComponent } from "./pages/chat-page.component";
import { ShellComponent } from "./shell/shell.component";

export const appRoutes: Routes = [
  {
    path: "",
    component: ShellComponent,
    children: [
      { path: "", pathMatch: "full", redirectTo: "chat" },
      { path: "chat", component: ChatPageComponent },
      { path: "assistants", redirectTo: "chat" },
      { path: "admin", component: AdminPageComponent }
    ]
  }
];
