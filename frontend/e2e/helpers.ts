import { Page, expect } from "@playwright/test";

/** Senha dos usuarios do realm de desenvolvimento (infra/keycloak/nexus-realm.json). */
export const PASSWORD = process.env["NEXUS_TEST_PASSWORD"] ?? "nexus-dev";

/** Login pelo formulario do Keycloak (fluxo Authorization Code + PKCE do app). */
export async function login(page: Page, username: string): Promise<void> {
  await page.goto("/");
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL(/\/chat/, { timeout: 30_000 });
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.locator("#username")).toBeVisible({ timeout: 30_000 });
}
