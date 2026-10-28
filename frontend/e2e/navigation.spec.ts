/**
 * SPEC-010: menu Administracao por papel (CT-81), volta ao chat pelo assistente
 * (CT-82), teclado (CT-83) e rota /admin removida (CT-84).
 *
 * O CT-82 intercepta a lista de assistentes e de conversas para nao depender dos
 * dados da pilha. Dados ficticios.
 */
import { Page, expect, test } from "@playwright/test";

import { login } from "./helpers";

const TRIGGER = '[data-testid="administration-menu-trigger"]';
const MENU = '[data-testid="administration-menu"]';

async function openMenuItems(page: Page): Promise<string[]> {
  await page.locator(TRIGGER).click();
  const menu = page.locator(MENU);
  await expect(menu).toBeVisible();
  return (await menu.getByRole("menuitem").allInnerTexts()).map((text) => text.trim());
}

test.describe("CT-81: menu Administracao conforme o papel", () => {
  test("admin ve os seis itens, na ordem da SPEC", async ({ page }) => {
    await login(page, "admin.nexus");
    expect(await openMenuItems(page)).toEqual([
      "Documentos e permissões",
      "Auditoria",
      "Conversas arquivadas",
      "Avaliações",
      "Consumo e limites",
      "Chaves de LLM"
    ]);
    await expect(page.getByTitle("Conversas", { exact: true })).toHaveCount(0);
  });

  test("curadora ve Documentos e permissoes e Avaliacoes", async ({ page }) => {
    await login(page, "curadora.rh");
    expect(await openMenuItems(page)).toEqual(["Documentos e permissões", "Avaliações"]);
  });

  test("usuario comum nao ve o botao Administracao, mas ve Sair", async ({ page }) => {
    await login(page, "usuario.rh");
    await expect(page.locator(TRIGGER)).toHaveCount(0);
    await expect(page.getByTitle("Conversas", { exact: true })).toHaveCount(0);
    await expect(page.getByTitle("Sair")).toBeVisible();
  });

  test("Chaves de LLM abre a tela de credenciais (SPEC-013)", async ({ page }) => {
    await login(page, "admin.nexus");
    await openMenuItems(page);
    await page.locator(MENU).getByRole("menuitem", { name: "Chaves de LLM" }).click();
    await expect(page.locator(MENU)).toHaveCount(0);
    await expect(page).toHaveURL(/\/admin\/llm-credentials$/);
    await expect(page.getByRole("heading", { name: "Chaves de LLM" })).toBeVisible();
  });
});

test("CT-82: na Auditoria, selecionar um assistente leva ao chat em branco", async ({ page }) => {
  const now = new Date().toISOString();
  await page.route("**/api/assistants", (route) =>
    route.request().method() !== "GET"
      ? route.fallback()
      : route.fulfill({
          json: [
            { id: "a-e2e", name: "Assistente E2E", description: null, initial_prompt: null, created_at: now }
          ]
        })
  );
  await page.route("**/api/assistants/a-e2e/conversations", (route) =>
    route.fulfill({
      json: [
        {
          id: "c-e2e",
          assistant_id: "a-e2e",
          name: "Conversa ficticia",
          created_at: now,
          updated_at: now,
          message_count: 2
        }
      ]
    })
  );

  await login(page, "admin.nexus");
  await page.goto("/admin/audit");
  const sidebar = page.locator("aside");
  // O menu lateral comeca recolhido; a lista de assistentes so aparece expandido.
  await sidebar.getByRole("button", { name: "Expandir menu" }).click();
  await sidebar.getByRole("button", { name: "Assistente E2E" }).click();

  await expect(page).toHaveURL(/\/chat$/);
  await expect(sidebar.getByRole("button", { name: "Conversa ficticia" })).toBeVisible();
  await expect(page.getByPlaceholder("Digite algo aqui")).toBeVisible();
});

test("CT-83: o menu funciona pelo teclado e fecha com clique fora", async ({ page }) => {
  await login(page, "admin.nexus");
  const trigger = page.locator(TRIGGER);

  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(MENU)).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(page.locator(MENU).getByRole("menuitem").nth(1)).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator(MENU)).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await trigger.click();
  await expect(page.locator(MENU)).toBeVisible();
  await page.mouse.click(900, 300);
  await expect(page.locator(MENU)).toHaveCount(0);
});

test("CT-84: a rota /admin foi removida e leva ao chat", async ({ page }) => {
  await login(page, "admin.nexus");
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/chat$/);
});
