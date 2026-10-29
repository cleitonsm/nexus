/**
 * SPEC-016: acesso rapido a assistentes na tela inicial (CT-129).
 *
 * Intercepta a lista de assistentes, o acesso rapido e as conversas para nao
 * depender dos dados da pilha; a escolha fica numa variavel do teste e sobrevive
 * ao recarregamento da pagina, como faria o servidor. Dados ficticios.
 */
import { Page, Route, expect, test } from "@playwright/test";

import { login } from "./helpers";

const NOW = new Date().toISOString();
const ASSISTANTS = [
  { id: "a-normativo", name: "Normativo E2E" },
  { id: "a-juridico", name: "Juridico E2E" },
  { id: "a-financeiro", name: "Financeiro E2E" },
  { id: "a-rh", name: "RH E2E" },
  { id: "a-ti", name: "TI E2E" }
].map((item) => ({ ...item, description: null, initial_prompt: null, created_at: NOW }));

interface HomeChoice {
  assistant_ids: string[];
  default_assistant_id: string;
}

/** Servidor ficticio do acesso rapido: D4 sem escolha, padrao primeiro (D7). */
async function mockApi(page: Page): Promise<{ saved: HomeChoice[] }> {
  const saved: HomeChoice[] = [];
  const home = (): object => {
    const choice = saved.at(-1);
    if (!choice) {
      return {
        assistant_ids: ASSISTANTS.slice(0, 4).map((item) => item.id),
        default_assistant_id: ASSISTANTS[0].id,
        max: 4,
        customized: false
      };
    }
    const others = choice.assistant_ids.filter((id) => id !== choice.default_assistant_id);
    return {
      assistant_ids: [choice.default_assistant_id, ...others],
      default_assistant_id: choice.default_assistant_id,
      max: 4,
      customized: true
    };
  };

  await page.route("**/api/assistants", (route) =>
    route.request().method() === "GET" ? route.fulfill({ json: ASSISTANTS }) : route.fallback()
  );
  await page.route("**/api/me/home-assistants", async (route: Route) => {
    if (route.request().method() === "PUT") {
      saved.push(route.request().postDataJSON() as HomeChoice);
    }
    await route.fulfill({ json: home() });
  });
  await page.route(/\/api\/assistants\/[^/]+\/conversations$/, (route) =>
    route.fulfill({ json: [] })
  );
  await page.route("**/api/conversations", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    const { assistant_id } = route.request().postDataJSON() as { assistant_id: string };
    return route.fulfill({
      json: {
        id: `c-${assistant_id}`,
        assistant_id,
        name: null,
        created_at: NOW,
        updated_at: NOW,
        message_count: 0
      }
    });
  });
  await page.route(/\/api\/conversations\/c-[^/]+$/, (route) => {
    const id = route.request().url().split("/").at(-1)!;
    return route.fulfill({
      json: { id, assistant_id: id.slice(2), created_at: NOW, updated_at: NOW, messages: [] }
    });
  });
  return { saved };
}

const cards = (page: Page) => page.getByTestId("home-assistants").getByRole("button");

async function cardNames(page: Page): Promise<string[]> {
  return (await cards(page).locator("p.text-sm").allInnerTexts()).map((text) => text.trim());
}

function card(page: Page, name: string) {
  return cards(page).filter({ hasText: name });
}

test.describe("CT-129: acesso rapido a assistentes (SPEC-016)", () => {
  test("sem escolha: quatro primeiros e o primeiro marcado como padrao (D4, D5)", async ({ page }) => {
    await mockApi(page);
    await login(page, "usuario.rh");

    await expect(cards(page)).toHaveCount(4);
    expect(await cardNames(page)).toEqual([
      "Normativo E2E",
      "Juridico E2E",
      "Financeiro E2E",
      "RH E2E"
    ]);
    await expect(card(page, "Normativo E2E")).toHaveAttribute("aria-pressed", "true");
    await expect(card(page, "Normativo E2E").getByTestId("home-default-badge")).toBeVisible();
    await expect(page.getByTestId("home-default-badge")).toHaveCount(1);
  });

  test("personalizar, recarregar e ver o padrao marcado (RF-103 a RF-107)", async ({ page }) => {
    const api = await mockApi(page);
    await login(page, "usuario.rh");

    await page.getByTestId("home-assistants-customize").click();
    const dialog = page.getByTestId("home-assistants-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByTestId("home-assistants-counter")).toHaveText("4 de 4");

    // No limite, quem nao esta marcado fica desabilitado (RN-47).
    await expect(dialog.getByRole("checkbox", { name: /TI E2E/ })).toBeDisabled();

    await dialog.getByRole("checkbox", { name: /Normativo E2E/ }).uncheck();
    await dialog.getByRole("checkbox", { name: /RH E2E/ }).uncheck();
    await dialog.getByRole("checkbox", { name: /TI E2E/ }).check();
    await expect(dialog.getByTestId("home-assistants-counter")).toHaveText("3 de 4");
    await dialog.getByRole("radio", { name: "Padrão: TI E2E" }).check();
    await dialog.getByTestId("home-assistants-save").click();

    await expect(dialog).toHaveCount(0);
    expect(api.saved.at(-1)).toEqual({
      assistant_ids: ["a-juridico", "a-financeiro", "a-ti"],
      default_assistant_id: "a-ti"
    });
    expect(await cardNames(page)).toEqual(["TI E2E", "Juridico E2E", "Financeiro E2E"]);
    await expect(card(page, "TI E2E")).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    await expect(cards(page)).toHaveCount(3);
    expect(await cardNames(page)).toEqual(["TI E2E", "Juridico E2E", "Financeiro E2E"]);
    await expect(card(page, "TI E2E")).toHaveAttribute("aria-pressed", "true");
    await expect(card(page, "TI E2E").getByTestId("home-default-badge")).toBeVisible();
  });

  test("sem padrao entre os marcados o modal nao salva; Cancelar fecha sem gravar", async ({ page }) => {
    const api = await mockApi(page);
    await login(page, "usuario.rh");

    await page.getByTestId("home-assistants-customize").click();
    const dialog = page.getByTestId("home-assistants-dialog");
    for (const name of ["Normativo E2E", "Juridico E2E", "Financeiro E2E", "RH E2E"]) {
      await dialog.getByRole("checkbox", { name: new RegExp(name) }).uncheck();
    }
    await expect(dialog.getByTestId("home-assistants-counter")).toHaveText("0 de 4");
    await expect(dialog.getByTestId("home-assistants-save")).toBeDisabled();

    await dialog.getByRole("button", { name: "Cancelar" }).click();
    await expect(dialog).toHaveCount(0);
    expect(api.saved).toEqual([]);
    await expect(cards(page)).toHaveCount(4);
  });

  test("Nova conversa volta ao assistente padrao (RF-105)", async ({ page }) => {
    await mockApi(page);
    await login(page, "usuario.rh");

    await card(page, "Financeiro E2E").click();
    await expect(card(page, "Financeiro E2E")).toHaveAttribute("aria-pressed", "true");

    const created = page.waitForRequest(
      (request) => request.method() === "POST" && request.url().endsWith("/api/conversations")
    );
    await page.getByRole("button", { name: "Nova conversa" }).click();
    expect((await created).postDataJSON()).toEqual({ assistant_id: "a-normativo" });
    await expect(card(page, "Normativo E2E")).toHaveAttribute("aria-pressed", "true");
  });
});
