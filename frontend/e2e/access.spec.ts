/**
 * FE-07 / E1 (RF-46, CT-32): login de cada papel, rotas conforme o papel e logout.
 * Cenarios E2 a E11 do plano seguem os roteiros manuais (docs/qa), com captura de tela.
 */
import { expect, test } from "@playwright/test";

import { login, logout } from "./helpers";

const ADMIN_ROUTES = ["/admin", "/admin/audit", "/admin/archived", "/admin/usage"];
const CURATOR_ROUTES = ["/assistants", "/feedback"];

const cases = [
  { user: "admin.nexus", allowed: [...ADMIN_ROUTES, ...CURATOR_ROUTES], denied: [] as string[] },
  { user: "curadora.rh", allowed: CURATOR_ROUTES, denied: ADMIN_ROUTES },
  { user: "usuario.rh", allowed: [], denied: [...ADMIN_ROUTES, ...CURATOR_ROUTES] },
  { user: "usuario.financeiro", allowed: [], denied: [...ADMIN_ROUTES, ...CURATOR_ROUTES] }
];

for (const { user, allowed, denied } of cases) {
  test(`E1: ${user} acessa so as rotas do seu papel e sai`, async ({ page }) => {
    await login(page, user);
    await page.screenshot({ path: `../docs/qa/relatorios/e2e/${user}-chat.png` });

    for (const route of allowed) {
      await page.goto(route);
      await expect(page, `${user} deveria acessar ${route}`).toHaveURL(new RegExp(`${route}$`));
    }
    for (const route of denied) {
      await page.goto(route);
      await expect(page, `${user} nao deveria acessar ${route}`).toHaveURL(/\/chat$/);
    }

    await logout(page);
  });
}

test("E1: sem sessao, qualquer rota leva ao login", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.locator("#username")).toBeVisible({ timeout: 30_000 });
});
